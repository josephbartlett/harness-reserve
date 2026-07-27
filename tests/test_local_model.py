from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from harness_reserve import cli
from harness_reserve.errors import PolicyError
from harness_reserve.local_model import propose_intent
from harness_reserve.util import strict_json_loads

from support import copied_example, load_example, read_manifest, write_manifest


class _FakeResponse:
    def __init__(
        self,
        payload: bytes,
        *,
        status: int = 200,
        content_length: str | None = None,
    ) -> None:
        self.status = status
        self._payload = payload
        self._content_length = content_length
        self._position = 0
        self.read_calls: list[int] = []

    def getheader(self, name: str) -> str | None:
        if name.lower() == "content-length":
            return self._content_length
        return None

    def read(self, amount: int) -> bytes:
        self.read_calls.append(amount)
        chunk = self._payload[self._position : self._position + amount]
        self._position += len(chunk)
        return chunk

    def read1(self, amount: int) -> bytes:
        return self.read(amount)


def _response_payload(
    content: str,
    *,
    reasoning: str | None = None,
) -> bytes:
    message: dict[str, object] = {
        "role": "assistant",
        "content": content,
    }
    if reasoning is not None:
        message["reasoning"] = reasoning
    return json.dumps(
        {
            "id": "synthetic-chat",
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _selection(
    action: str = "status",
    parameters: dict[str, object] | None = None,
    confidence: object = 0.91,
) -> str:
    return json.dumps(
        {
            "decision": "select",
            "action": action,
            "parameters": parameters or {},
            "confidence": confidence,
        },
        separators=(",", ":"),
    )


class LocalModelProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._ignore_patcher = patch(
            "harness_reserve.local_model.is_path_ignored",
            return_value=True,
        )
        self._ignore_patcher.start()
        self.addCleanup(self._ignore_patcher.stop)

    def _connection(
        self,
        payload: bytes,
        *,
        status: int = 200,
        content_length: str | None = None,
    ) -> tuple[MagicMock, _FakeResponse]:
        response = _FakeResponse(
            payload,
            status=status,
            content_length=content_length,
        )
        connection = MagicMock()
        connection.getresponse.return_value = response
        return connection, response

    def test_success_uses_one_fixed_loopback_call_and_writes_only_intent(
        self,
    ) -> None:
        private_request = "PRIVATE-REQUEST-MARKER: report readiness"
        private_reasoning = "PRIVATE-REASONING-MARKER"
        with copied_example() as root:
            value = read_manifest(root)
            value["project"]["display_name"] = "PRIVATE-PROJECT-MARKER"
            value["actions"]["status"]["fixed_args"] = ["PRIVATE-FIXED-MARKER"]
            value["actions"]["status"]["environment"] = {
                "PRIVATE_ENV": "PRIVATE-ENV-MARKER"
            }
            value["actions"]["process"]["model_invocable"] = True
            value["actions"]["verify"]["model_invocable"] = True
            value["actions"]["verify"]["confirmation"] = {
                "mode": "explicit",
                "prompt": "Human review required.",
            }
            value["actions"]["serve-private"]["model_invocable"] = True
            value["actions"]["use"]["model_invocable"] = True
            value["actions"]["use"]["parameters"] = {
                "secret-token": {
                    "type": "string",
                    "flag": "--secret-token",
                    "required": False,
                    "sensitive": True,
                }
            }
            write_manifest(root, value)
            manifest = load_example(root)
            connection, response = self._connection(
                _response_payload(
                    _selection(),
                    reasoning=private_reasoning,
                )
            )

            with patch(
                "harness_reserve.local_model.http.client.HTTPConnection",
                return_value=connection,
            ) as factory:
                result = propose_intent(
                    manifest,
                    request=private_request,
                )

            factory.assert_called_once_with("127.0.0.1", 11434, timeout=300)
            connection.request.assert_called_once()
            method, path = connection.request.call_args.args[:2]
            self.assertEqual((method, path), ("POST", "/v1/chat/completions"))
            request_body = connection.request.call_args.kwargs["body"]
            headers = connection.request.call_args.kwargs["headers"]
            self.assertEqual(
                headers,
                {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            self.assertNotIn("Authorization", headers)
            envelope = strict_json_loads(request_body.decode("utf-8"))
            self.assertEqual(envelope["model"], "gpt-oss:20b")
            self.assertFalse(envelope["stream"])
            self.assertTrue(
                envelope["messages"][0]["content"].startswith("Reasoning: low")
            )
            self.assertNotIn("tools", envelope)
            self.assertNotIn("tool_choice", envelope)
            user_message = strict_json_loads(envelope["messages"][1]["content"])
            self.assertEqual(user_message["request"], private_request)
            catalog_actions = user_message["eligible_actions"]
            self.assertEqual(
                [item["action"] for item in catalog_actions],
                ["process", "status"],
            )
            catalog_text = json.dumps(catalog_actions)
            for forbidden in (
                ".harness-reserve/actions",
                "--item",
                "--open-after",
                "PRIVATE-FIXED-MARKER",
                "PRIVATE_ENV",
                "PRIVATE-ENV-MARKER",
                "PRIVATE-PROJECT-MARKER",
                "serve-private",
                "verify",
                '"use"',
                "working_directory",
                "entrypoint",
                "authority",
            ):
                self.assertNotIn(forbidden, catalog_text)
            self.assertGreaterEqual(len(response.read_calls), 2)
            self.assertTrue(all(amount <= 8192 for amount in response.read_calls))
            connection.close.assert_called_once_with()

            self.assertTrue(result.plan["dry_run"])
            self.assertFalse(result.plan["executed"])
            self.assertEqual(result.plan["action"], "status")
            self.assertEqual(result.plan["provider"], "ollama-loopback")
            self.assertEqual(result.plan["model"], "gpt-oss:20b")
            self.assertIsNone(result.plan.get("receipt_path"))
            self.assertTrue(result.intent_path.is_file())
            self.assertEqual(
                result.intent_path.parent,
                manifest.state_directory / "intents",
            )
            stored = strict_json_loads(result.intent_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(stored),
                {
                    "contract_version",
                    "project_id",
                    "action",
                    "parameters",
                    "reason",
                    "confidence",
                },
            )
            self.assertEqual(stored["action"], "status")
            self.assertEqual(stored["parameters"], {})
            self.assertNotIn(private_request, json.dumps(stored))
            self.assertNotIn(private_reasoning, json.dumps(stored))
            self.assertFalse((manifest.state_directory / "latest.json").exists())
            self.assertFalse((manifest.state_directory / "runs").exists())

    def test_exact_refusal_blocks_without_writing_an_intent(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            connection, _ = self._connection(
                _response_payload('{"decision":"refuse"}')
            )
            with patch(
                "harness_reserve.local_model.http.client.HTTPConnection",
                return_value=connection,
            ):
                with self.assertRaisesRegex(
                    PolicyError,
                    "declined to select",
                ):
                    propose_intent(manifest, request="Do something unsuitable.")
            self.assertFalse((manifest.state_directory / "intents").exists())

    def test_internal_response_variants_are_closed(self) -> None:
        invalid_contents = {
            "refusal extra field": '{"decision":"refuse","reason":"PRIVATE"}',
            "selection extra field": (
                '{"decision":"select","action":"status","parameters":{},'
                '"confidence":0.8,"command":"PRIVATE"}'
            ),
            "selection missing field": (
                '{"decision":"select","action":"status","parameters":{}}'
            ),
            "unknown decision": '{"decision":"maybe"}',
            "duplicate field": (
                '{"decision":"select","action":"status","action":"status",'
                '"parameters":{},"confidence":0.8}'
            ),
            "nonfinite confidence": (
                '{"decision":"select","action":"status","parameters":{},'
                '"confidence":NaN}'
            ),
            "prose": "I would choose status.",
        }
        for label, content in invalid_contents.items():
            with self.subTest(label=label), copied_example() as root:
                manifest = load_example(root)
                connection, _ = self._connection(_response_payload(content))
                with patch(
                    "harness_reserve.local_model.http.client.HTTPConnection",
                    return_value=connection,
                ):
                    with self.assertRaises(PolicyError) as caught:
                        propose_intent(manifest, request="Report status.")
                self.assertNotIn("PRIVATE", str(caught.exception))
                self.assertFalse((manifest.state_directory / "intents").exists())

    def test_provider_envelope_is_strict_json_and_raw_content_is_not_reported(
        self,
    ) -> None:
        invalid_payloads = {
            "duplicate": (
                b'{"choices":[],"choices":[{"message":{"content":"PRIVATE"}}]}'
            ),
            "nonfinite": b'{"score":NaN,"choices":[]}',
            "malformed": b'{"choices":["PRIVATE"',
            "wrong shape": b'["PRIVATE"]',
            "multiple choices": json.dumps(
                {
                    "choices": [
                        {"message": {"content": _selection()}},
                        {"message": {"content": "PRIVATE"}},
                    ]
                }
            ).encode("utf-8"),
            "non-string content": b'{"choices":[{"message":{"content":null}}]}',
        }
        for label, payload in invalid_payloads.items():
            with self.subTest(label=label), copied_example() as root:
                connection, _ = self._connection(payload)
                with patch(
                    "harness_reserve.local_model.http.client.HTTPConnection",
                    return_value=connection,
                ):
                    with self.assertRaises(PolicyError) as caught:
                        propose_intent(load_example(root), request="Report status.")
                self.assertNotIn("PRIVATE", str(caught.exception))

    def test_provider_tool_calls_are_rejected(self) -> None:
        payload = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": _selection(),
                            "tool_calls": [],
                            "reasoning": "PRIVATE-REASONING-MARKER",
                        }
                    }
                ]
            },
            separators=(",", ":"),
        ).encode("utf-8")
        with copied_example() as root:
            connection, _ = self._connection(payload)
            with patch(
                "harness_reserve.local_model.http.client.HTTPConnection",
                return_value=connection,
            ):
                with self.assertRaises(PolicyError) as caught:
                    propose_intent(load_example(root), request="Report status.")
            self.assertNotIn("PRIVATE", str(caught.exception))
            self.assertFalse((root / ".harness-reserve/state/intents").exists())

    def test_hallucinated_or_invalid_selection_fails_existing_policy(self) -> None:
        cases = {
            "not catalogued": _selection("verify"),
            "unknown parameter": _selection("status", {"command": "PRIVATE"}),
            "boolean confidence": _selection(confidence=True),
            "confidence high": _selection(confidence=1.1),
            "parameters not object": (
                '{"decision":"select","action":"status","parameters":[],'
                '"confidence":0.8}'
            ),
        }
        for label, content in cases.items():
            with self.subTest(label=label), copied_example() as root:
                connection, _ = self._connection(_response_payload(content))
                with patch(
                    "harness_reserve.local_model.http.client.HTTPConnection",
                    return_value=connection,
                ):
                    with self.assertRaises(PolicyError) as caught:
                        propose_intent(load_example(root), request="Report status.")
                self.assertNotIn("PRIVATE", str(caught.exception))
                self.assertFalse((root / ".harness-reserve/state/intents").exists())

    def test_request_and_timeout_limits_fail_before_transport(self) -> None:
        cases = [
            ("", 300),
            (" ", 300),
            ("bad\x00request", 300),
            ("\ud800", 300),
            ("x" * 2001, 300),
            ("okay", 4),
            ("okay", 901),
            ("okay", True),
        ]
        for request, timeout in cases:
            with self.subTest(request_length=len(request), timeout=timeout):
                with copied_example() as root, patch(
                    "harness_reserve.local_model.http.client.HTTPConnection"
                ) as factory:
                    with self.assertRaises(PolicyError):
                        propose_intent(
                            load_example(root),
                            request=request,
                            timeout_seconds=timeout,
                        )
                    factory.assert_not_called()

    def test_unignored_intent_storage_blocks_before_transport(self) -> None:
        with copied_example() as root:
            with (
                patch(
                "harness_reserve.local_model.is_path_ignored",
                return_value=False,
                ),
                patch(
                    "harness_reserve.local_model.http.client.HTTPConnection"
                ) as factory,
            ):
                with self.assertRaisesRegex(PolicyError, "verified as ignored"):
                    propose_intent(load_example(root), request="Report status.")
                factory.assert_not_called()

    def test_unknown_ignore_state_blocks_before_transport(self) -> None:
        with copied_example() as root:
            with (
                patch(
                    "harness_reserve.local_model.is_path_ignored",
                    return_value=None,
                ),
                patch(
                    "harness_reserve.local_model.http.client.HTTPConnection"
                ) as factory,
            ):
                with self.assertRaisesRegex(PolicyError, "verified as ignored"):
                    propose_intent(load_example(root), request="Report status.")
                factory.assert_not_called()

    def test_intents_use_the_fixed_reserved_directory(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["state"] = {
                "directory": ".harness-reserve/state/custom-runtime",
                "handoff_directory": (
                    ".harness-reserve/state/custom-runtime/handoffs"
                ),
            }
            write_manifest(root, value)
            connection, _ = self._connection(_response_payload(_selection()))
            with patch(
                "harness_reserve.local_model.http.client.HTTPConnection",
                return_value=connection,
            ):
                result = propose_intent(
                    load_example(root),
                    request="Report status.",
                )
            self.assertEqual(
                result.intent_path.parent,
                root / ".harness-reserve/state/intents",
            )
            self.assertFalse(
                (root / ".harness-reserve/state/custom-runtime/intents").exists()
            )

    def test_catalog_limit_fails_before_transport(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["actions"]["status"]["description"] = "x" * (33 * 1024)
            write_manifest(root, value)
            with patch(
                "harness_reserve.local_model.http.client.HTTPConnection"
            ) as factory:
                with self.assertRaisesRegex(PolicyError, "catalog exceeds"):
                    propose_intent(load_example(root), request="Report status.")
                factory.assert_not_called()

    def test_request_envelope_limit_fails_before_transport(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["actions"]["status"]["description"] = "\\" * 15_900
            write_manifest(root, value)
            with patch(
                "harness_reserve.local_model.http.client.HTTPConnection"
            ) as factory:
                with self.assertRaisesRegex(PolicyError, "envelope exceeds"):
                    propose_intent(
                        load_example(root),
                        request="x" * 2000,
                    )
                factory.assert_not_called()

    def test_response_and_content_limits_are_enforced(self) -> None:
        cases = [
            (
                "declared envelope",
                _response_payload(_selection()),
                str(64 * 1024 + 1),
                "response envelope exceeds",
            ),
            (
                "read envelope",
                b"x" * (64 * 1024 + 1),
                None,
                "response envelope exceeds",
            ),
            (
                "content",
                _response_payload("x" * (16 * 1024 + 1)),
                None,
                "response content exceeds",
            ),
        ]
        for label, payload, content_length, expected in cases:
            with self.subTest(label=label), copied_example() as root:
                connection, response = self._connection(
                    payload,
                    content_length=content_length,
                )
                with patch(
                    "harness_reserve.local_model.http.client.HTTPConnection",
                    return_value=connection,
                ):
                    with self.assertRaisesRegex(PolicyError, expected):
                        propose_intent(
                            load_example(root),
                            request="Report status.",
                        )
                if label == "declared envelope":
                    self.assertEqual(response.read_calls, [])

    def test_transport_and_http_failures_are_safe_and_never_retried(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            failed_connection = MagicMock()
            failed_connection.request.side_effect = OSError(
                "PRIVATE-REQUEST-AND-ENDPOINT-MARKER"
            )
            with patch(
                "harness_reserve.local_model.http.client.HTTPConnection",
                return_value=failed_connection,
            ) as factory:
                with self.assertRaises(PolicyError) as caught:
                    propose_intent(
                        manifest,
                        request="PRIVATE-USER-REQUEST",
                        timeout_seconds=17,
                    )
            factory.assert_called_once_with("127.0.0.1", 11434, timeout=17)
            failed_connection.request.assert_called_once()
            self.assertNotIn("PRIVATE", str(caught.exception))
            failed_connection.close.assert_called_once_with()

        with copied_example() as root:
            connection, _ = self._connection(
                b'{"error":"PRIVATE-PROVIDER-ERROR"}',
                status=503,
            )
            with patch(
                "harness_reserve.local_model.http.client.HTTPConnection",
                return_value=connection,
            ):
                with self.assertRaises(PolicyError) as caught:
                    propose_intent(load_example(root), request="Report status.")
            self.assertNotIn("PRIVATE", str(caught.exception))
            connection.getresponse.assert_called_once_with()

    def test_timeout_is_a_total_wall_clock_deadline(self) -> None:
        with copied_example() as root:
            connection, _ = self._connection(_response_payload(_selection()))
            with (
                patch(
                    "harness_reserve.local_model.http.client.HTTPConnection",
                    return_value=connection,
                ),
                patch(
                    "harness_reserve.local_model.time.monotonic",
                    side_effect=[100.0, 106.0],
                ),
            ):
                with self.assertRaisesRegex(PolicyError, "total timeout"):
                    propose_intent(
                        load_example(root),
                        request="Report status.",
                        timeout_seconds=5,
                    )
            connection.request.assert_called_once()
            connection.getresponse.assert_not_called()
            connection.close.assert_called_once_with()

    def test_typed_parameters_use_existing_intent_policy(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["actions"]["process"]["model_invocable"] = True
            write_manifest(root, value)
            manifest = load_example(root)
            connection, _ = self._connection(
                _response_payload(
                    _selection(
                        "process",
                        {"item": "safe-token", "open-after": True},
                    )
                )
            )
            with patch(
                "harness_reserve.local_model.http.client.HTTPConnection",
                return_value=connection,
            ):
                result = propose_intent(manifest, request="Process safe-token.")
            self.assertEqual(
                result.intent["parameters"],
                {"item": "safe-token", "open-after": True},
            )

        with copied_example() as root:
            value = read_manifest(root)
            value["actions"]["process"]["model_invocable"] = True
            write_manifest(root, value)
            connection, _ = self._connection(
                _response_payload(
                    _selection(
                        "process",
                        {"item": "../private-path", "open-after": False},
                    )
                )
            )
            with patch(
                "harness_reserve.local_model.http.client.HTTPConnection",
                return_value=connection,
            ):
                with self.assertRaisesRegex(
                    PolicyError,
                    "failed deterministic intent validation",
                ):
                    propose_intent(
                        load_example(root),
                        request="Process an unsafe path.",
                    )
            self.assertFalse((root / ".harness-reserve/state/intents").exists())

    def test_storage_is_collision_safe_and_does_not_overwrite(self) -> None:
        class _FixedDateTime:
            @classmethod
            def now(cls, tz: object) -> datetime:
                self.assertIs(tz, timezone.utc)
                return datetime(2026, 7, 27, 12, 34, 56, tzinfo=timezone.utc)

        with copied_example() as root:
            manifest = load_example(root)
            directory = manifest.state_directory / "intents"
            directory.mkdir(parents=True)
            existing = directory / "20260727T123456Z-aaaaaaaaaaaa.intent.json"
            existing.write_text("ORIGINAL\n", encoding="utf-8")
            connection, _ = self._connection(_response_payload(_selection()))
            identifiers = [
                SimpleNamespace(hex="aaaaaaaaaaaa0000"),
                SimpleNamespace(hex="bbbbbbbbbbbb0000"),
            ]
            with (
                patch(
                    "harness_reserve.local_model.http.client.HTTPConnection",
                    return_value=connection,
                ),
                patch(
                    "harness_reserve.local_model.datetime",
                    _FixedDateTime,
                ),
                patch(
                    "harness_reserve.local_model.uuid.uuid4",
                    side_effect=identifiers,
                ),
            ):
                result = propose_intent(manifest, request="Report status.")
            self.assertEqual(existing.read_text(encoding="utf-8"), "ORIGINAL\n")
            self.assertEqual(
                result.intent_path.name,
                "20260727T123456Z-bbbbbbbbbbbb.intent.json",
            )
            self.assertTrue(result.intent_path.is_file())
            self.assertEqual(
                list(directory.glob("*.tmp")),
                [],
            )

    def test_storage_revalidates_the_directory_after_provider_wait(self) -> None:
        with copied_example() as root:
            directory = root / ".harness-reserve/state/intents"
            connection, _ = self._connection(_response_payload(_selection()))
            with (
                patch(
                    "harness_reserve.local_model.http.client.HTTPConnection",
                    return_value=connection,
                ),
                patch(
                    "harness_reserve.local_model._intent_directory",
                    side_effect=[
                        directory,
                        directory,
                        PolicyError(
                            "BLOCK: Synthetic directory replacement detected."
                        ),
                    ],
                ) as directory_check,
            ):
                with self.assertRaisesRegex(PolicyError, "replacement detected"):
                    propose_intent(
                        load_example(root),
                        request="Report status.",
                    )
            self.assertEqual(directory_check.call_count, 3)
            self.assertTrue(directory.is_dir())
            self.assertEqual(list(directory.iterdir()), [])
            self.assertFalse((root / ".harness-reserve/state/latest.json").exists())

    def test_storage_failure_is_safe_and_leaves_no_partial_intent(self) -> None:
        with copied_example() as root:
            connection, _ = self._connection(_response_payload(_selection()))
            with (
                patch(
                    "harness_reserve.local_model.http.client.HTTPConnection",
                    return_value=connection,
                ),
                patch(
                    "harness_reserve.local_model.os.link",
                    side_effect=PermissionError("PRIVATE-STORAGE-PATH"),
                ),
            ):
                with self.assertRaises(PolicyError) as caught:
                    propose_intent(
                        load_example(root),
                        request="PRIVATE-USER-REQUEST",
                    )
            self.assertNotIn("PRIVATE", str(caught.exception))
            directory = root / ".harness-reserve/state/intents"
            self.assertEqual(list(directory.glob("*")), [])
            self.assertFalse((root / ".harness-reserve/state/latest.json").exists())

    def test_cli_surface_is_proposal_only_and_json_reports_no_execution(
        self,
    ) -> None:
        with copied_example() as root:
            connection, _ = self._connection(_response_payload(_selection()))
            stdout = io.StringIO()
            with (
                patch(
                    "harness_reserve.local_model.http.client.HTTPConnection",
                    return_value=connection,
                ),
                redirect_stdout(stdout),
            ):
                exit_code = cli.main(
                    [
                        "--project-root",
                        str(root),
                        "--json",
                        "propose-intent",
                        "--request",
                        "Report status.",
                        "--timeout-seconds",
                        "23",
                    ]
                )
            self.assertEqual(exit_code, 0)
            output = strict_json_loads(stdout.getvalue())
            self.assertTrue(output["dry_run"])
            self.assertFalse(output["executed"])
            self.assertEqual(output["action"], "status")
            self.assertFalse((root / ".harness-reserve/state/runs").exists())
            self.assertFalse((root / ".harness-reserve/state/latest.json").exists())

            human_connection, _ = self._connection(
                _response_payload(_selection())
            )
            human_stdout = io.StringIO()
            with (
                patch(
                    "harness_reserve.local_model.http.client.HTTPConnection",
                    return_value=human_connection,
                ),
                redirect_stdout(human_stdout),
            ):
                human_exit = cli.main(
                    [
                        "--project-root",
                        str(root),
                        "propose-intent",
                        "--request",
                        "Report status.",
                    ]
                )
            self.assertEqual(human_exit, 0)
            human_output = human_stdout.getvalue()
            for expected in (
                "Action: status",
                "Runner: python",
                "Entrypoint:",
                "Working directory:",
                "Parameters: {}",
                "Authority:",
                "Intent:",
                "No action was executed",
            ):
                self.assertIn(expected, human_output)

            for forbidden in (
                "--execute",
                "--confirm",
                "--confirmation-text",
                "--model",
                "--endpoint",
            ):
                with self.subTest(forbidden=forbidden):
                    stderr = io.StringIO()
                    extra = [forbidden]
                    if forbidden in {
                        "--confirmation-text",
                        "--model",
                        "--endpoint",
                    }:
                        extra.append("value")
                    with redirect_stderr(stderr), self.assertRaises(SystemExit) as caught:
                        cli._parser().parse_args(
                            [
                                "propose-intent",
                                "--request",
                                "Report status.",
                                *extra,
                            ]
                        )
                    self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
