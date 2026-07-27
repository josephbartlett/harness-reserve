from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from harness_reserve.cli import _print_execution
from harness_reserve.runner import _run_process, execute_action

from support import copied_example, load_example, read_manifest, write_manifest

LOW_AUTHORITY = {
    "filesystem": "read-only",
    "network": "none",
    "git": "none",
    "external_systems": "none",
    "secrets": "none",
    "semantic_authority": "none",
}


class RunnerTests(unittest.TestCase):
    def test_status_writes_aggregate_receipt(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            result = execute_action(manifest, "status", {})
            self.assertEqual(result.receipt["execution"]["outcome"], "PASS")
            self.assertEqual(result.receipt["result"]["project_state"], "READY")
            self.assertFalse(result.receipt["privacy"]["stdout_stored"])
            self.assertNotIn("example status is ready", json.dumps(result.receipt))
            self.assertTrue(result.receipt_path and result.receipt_path.is_file())

    def test_python_runner_uses_utf8_without_writing_bytecode(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            result = execute_action(manifest, "status", {})
            self.assertEqual(result.receipt["execution"]["outcome"], "PASS")
            self.assertEqual(
                result.command_preview[1:4],
                ["-X", "utf8", "-B"],
            )
            self.assertFalse(
                any(root.rglob("__pycache__")),
                "Python action execution must not dirty the adopting project.",
            )

    def test_process_binds_typed_parameters(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            result = execute_action(
                manifest,
                "process",
                {"item": "sample-1", "open-after": True},
            )
            self.assertEqual(result.receipt["execution"]["outcome"], "PASS")
            output = root / ".harness-reserve" / "state" / "processed-items.txt"
            self.assertEqual(output.read_text(encoding="utf-8"), "sample-1\n")

    def test_exact_native_executable_runner_uses_contained_argv(self) -> None:
        source = (
            shutil.which("whoami.exe") or shutil.which("whoami")
            if os.name == "nt"
            else shutil.which("true")
        )
        if source is None:
            self.skipTest("No small native executable is available for the probe.")
        with copied_example() as root:
            suffix = ".exe" if os.name == "nt" else ""
            relative = f".harness-reserve/actions/native-probe{suffix}"
            destination = root / Path(relative)
            shutil.copy2(source, destination)
            value = read_manifest(root)
            value["actions"]["native-probe"] = {
                "description": "Execute one exact contained native binary.",
                "runner": "executable",
                "entrypoint": relative,
                "working_directory": ".",
                "fixed_args": [],
                "parameters": {},
                "environment": {},
                "timeout_seconds": 60,
                "authority": LOW_AUTHORITY,
                "confirmation": {"mode": "none", "prompt": "Synthetic test."},
                "model_invocable": False,
            }
            write_manifest(root, value)
            result = execute_action(load_example(root), "native-probe", {})
            self.assertEqual(result.receipt["execution"]["outcome"], "PASS")
            self.assertEqual(result.command_preview, [str(destination.resolve())])

    def test_dry_run_does_not_execute(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            result = execute_action(manifest, "use", {}, dry_run=True)
            self.assertTrue(result.receipt["dry_run"])
            marker = root / ".harness-reserve" / "state" / "example-app-opened.txt"
            self.assertFalse(marker.exists())
            self.assertIsNone(result.receipt_path)

    def test_sensitive_parameter_is_redacted_and_stdout_not_stored(self) -> None:
        with copied_example() as root:
            action_path = root / ".harness-reserve" / "actions" / "sensitive.py"
            action_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "import argparse, json, os",
                        "from pathlib import Path",
                        "p = argparse.ArgumentParser()",
                        "p.add_argument('--token', required=True)",
                        "a = p.parse_args()",
                        "print('PRIVATE-' + a.token)",
                        "payload = {'contract_version': 1, 'outcome': 'PASS', 'safe_summary': 'Sensitive test passed.', 'project_state': 'READY', 'warnings': [], 'evidence': [], 'next_action': None}",
                        "Path(os.environ['HARNESS_RESERVE_RESULT_PATH']).write_text(json.dumps(payload) + '\\n', encoding='utf-8')",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            value = read_manifest(root)
            value["actions"]["sensitive-test"] = {
                "description": "Test sensitive parameter redaction.",
                "runner": "python",
                "entrypoint": ".harness-reserve/actions/sensitive.py",
                "working_directory": ".",
                "fixed_args": [],
                "parameters": {
                    "token": {
                        "type": "string",
                        "flag": "--token",
                        "required": True,
                        "sensitive": True,
                    }
                },
                "environment": {},
                "timeout_seconds": 60,
                "authority": {
                    "filesystem": "read-only",
                    "network": "none",
                    "git": "none",
                    "external_systems": "none",
                    "secrets": "none",
                    "semantic_authority": "none",
                },
                "confirmation": {"mode": "none", "prompt": "Test only."},
                "model_invocable": False,
            }
            write_manifest(root, value)
            manifest = load_example(root)
            dry_run = execute_action(
                manifest,
                "sensitive-test",
                {"token": "DO-NOT-STORE"},
                dry_run=True,
            )
            self.assertNotIn("DO-NOT-STORE", json.dumps(dry_run.receipt))
            result = execute_action(
                manifest, "sensitive-test", {"token": "DO-NOT-STORE"}
            )
            serialized = json.dumps(result.receipt)
            self.assertEqual(
                result.receipt["invocation"]["parameters"]["token"], "<redacted>"
            )
            self.assertNotIn("DO-NOT-STORE", serialized)
            self.assertIn("PRIVATE-DO-NOT-STORE", result.stdout)
            self.assertNotIn("DO-NOT-STORE", json.dumps(result.command_preview))
            json_stdout = StringIO()
            json_stderr = StringIO()
            with redirect_stdout(json_stdout), redirect_stderr(json_stderr):
                exit_code = _print_execution(result, as_json=True)
            self.assertEqual(exit_code, 0)
            self.assertNotIn("DO-NOT-STORE", json_stdout.getvalue())
            self.assertNotIn("PRIVATE-", json_stdout.getvalue())
            self.assertEqual(json_stderr.getvalue(), "")

    def test_nonzero_exit_cannot_be_overridden_by_false_pass(self) -> None:
        with copied_example() as root:
            action_path = root / ".harness-reserve" / "actions" / "false_pass.py"
            action_path.write_text(
                "\n".join(
                    [
                        "import json, os",
                        "from pathlib import Path",
                        "payload = {'contract_version': 1, 'outcome': 'PASS', 'safe_summary': 'Incorrect pass.', 'project_state': 'READY', 'warnings': [], 'evidence': [], 'next_action': None}",
                        "Path(os.environ['HARNESS_RESERVE_RESULT_PATH']).write_text(json.dumps(payload) + '\\n', encoding='utf-8')",
                        "raise SystemExit(20)",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            value = read_manifest(root)
            value["actions"]["false-pass"] = {
                "description": "Prove conservative outcome reconciliation.",
                "runner": "python",
                "entrypoint": ".harness-reserve/actions/false_pass.py",
                "working_directory": ".",
                "fixed_args": [],
                "parameters": {},
                "environment": {},
                "timeout_seconds": 60,
                "authority": LOW_AUTHORITY,
                "confirmation": {"mode": "none", "prompt": "Test only."},
                "model_invocable": False,
            }
            write_manifest(root, value)
            result = execute_action(load_example(root), "false-pass", {})
            self.assertEqual(result.receipt["execution"]["outcome"], "BLOCK")
            self.assertIsNone(result.receipt["result"]["safe_summary"])
            self.assertEqual(result.receipt["result"]["project_state"], "UNKNOWN")
            self.assertTrue(result.receipt["result"]["warnings"])

    def test_malformed_action_result_becomes_error(self) -> None:
        with copied_example() as root:
            action_path = root / ".harness-reserve" / "actions" / "bad_result.py"
            action_path.write_text(
                "from pathlib import Path\nimport os\nPath(os.environ['HARNESS_RESERVE_RESULT_PATH']).write_text('{bad', encoding='utf-8')\n",
                encoding="utf-8",
            )
            value = read_manifest(root)
            value["actions"]["bad-result"] = {
                "description": "Prove malformed results fail closed.",
                "runner": "python",
                "entrypoint": ".harness-reserve/actions/bad_result.py",
                "working_directory": ".",
                "fixed_args": [],
                "parameters": {},
                "environment": {},
                "timeout_seconds": 60,
                "authority": LOW_AUTHORITY,
                "confirmation": {"mode": "none", "prompt": "Test only."},
                "model_invocable": False,
            }
            write_manifest(root, value)
            result = execute_action(load_example(root), "bad-result", {})
            self.assertEqual(result.receipt["execution"]["outcome"], "ERROR")
            self.assertTrue(result.receipt["result"]["warnings"])
            self.assertTrue(result.receipt["result"]["action_result_present"])
            self.assertFalse(result.receipt["result"]["action_result_valid"])

    def test_invalid_action_result_field_names_do_not_leak_to_receipt(self) -> None:
        with copied_example() as root:
            action_path = root / ".harness-reserve" / "actions" / "private_field.py"
            private_marker = "PRIVATE-UNKNOWN-FIELD-" + ("X" * 1200)
            action_path.write_text(
                "\n".join(
                    [
                        "import json, os",
                        "from pathlib import Path",
                        f"private_key = {private_marker!r}",
                        "payload = {'contract_version': 1, 'outcome': 'PASS', private_key: True}",
                        "Path(os.environ['HARNESS_RESERVE_RESULT_PATH']).write_text(json.dumps(payload), encoding='utf-8')",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            value = read_manifest(root)
            value["actions"]["private-field"] = {
                "description": "Prove invalid result diagnostics remain aggregate.",
                "runner": "python",
                "entrypoint": ".harness-reserve/actions/private_field.py",
                "working_directory": ".",
                "fixed_args": [],
                "parameters": {},
                "environment": {},
                "timeout_seconds": 60,
                "authority": LOW_AUTHORITY,
                "confirmation": {"mode": "none", "prompt": "Test only."},
                "model_invocable": False,
            }
            write_manifest(root, value)
            result = execute_action(load_example(root), "private-field", {})
            serialized = json.dumps(result.receipt)
            self.assertEqual(result.receipt["execution"]["outcome"], "ERROR")
            self.assertNotIn("PRIVATE-UNKNOWN-FIELD", serialized)
            self.assertTrue(
                all(
                    len(warning) <= 1000
                    for warning in result.receipt["result"]["warnings"]
                )
            )

    def test_timeout_becomes_error(self) -> None:
        with copied_example() as root:
            action_path = root / ".harness-reserve" / "actions" / "slow.py"
            action_path.write_text("import time\ntime.sleep(3)\n", encoding="utf-8")
            value = read_manifest(root)
            value["actions"]["slow"] = {
                "description": "Prove timeout handling.",
                "runner": "python",
                "entrypoint": ".harness-reserve/actions/slow.py",
                "working_directory": ".",
                "fixed_args": [],
                "parameters": {},
                "environment": {},
                "timeout_seconds": 1,
                "authority": LOW_AUTHORITY,
                "confirmation": {"mode": "none", "prompt": "Test only."},
                "model_invocable": False,
            }
            write_manifest(root, value)
            result = execute_action(load_example(root), "slow", {})
            self.assertEqual(result.receipt["execution"]["outcome"], "ERROR")
            self.assertTrue(result.receipt["execution"]["timed_out"])

    def test_timeout_final_pipe_drain_is_bounded(self) -> None:
        class SyntheticPipe:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

        class SyntheticProcess:
            def __init__(self) -> None:
                self.pid = 12345
                self.returncode = None
                self.stdout = SyntheticPipe()
                self.stderr = SyntheticPipe()
                self.communicate_calls = 0
                self.kill_calls = 0
                self.wait_calls = 0

            def communicate(
                self,
                timeout: int | None = None,
            ) -> tuple[str, str]:
                self.communicate_calls += 1
                raise subprocess.TimeoutExpired(
                    cmd=["synthetic"],
                    timeout=timeout or 0,
                    output=b"partial stdout",
                    stderr=b"partial stderr",
                )

            def kill(self) -> None:
                self.kill_calls += 1

            def wait(self, timeout: int | None = None) -> int:
                self.wait_calls += 1
                raise subprocess.TimeoutExpired(
                    cmd=["synthetic"],
                    timeout=timeout or 0,
                )

        process = SyntheticProcess()
        with (
            patch(
                "harness_reserve.runner.subprocess.Popen",
                return_value=process,
            ),
            patch(
                "harness_reserve.runner._terminate_process_tree",
                return_value=None,
            ),
        ):
            capture = _run_process(
                ["synthetic"],
                working_directory=Path.cwd(),
                environment=os.environ.copy(),
                timeout_seconds=1,
            )

        self.assertTrue(capture.timed_out)
        self.assertEqual(process.communicate_calls, 2)
        self.assertEqual(process.kill_calls, 1)
        self.assertEqual(process.wait_calls, 1)
        self.assertTrue(process.stdout.closed)
        self.assertTrue(process.stderr.closed)
        self.assertEqual(capture.stdout, "partial stdout")
        self.assertEqual(capture.stderr, "partial stderr")
        self.assertIn("bounded termination", capture.termination_warning or "")

    def test_process_start_error_becomes_error_receipt(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            with patch(
                "harness_reserve.runner.subprocess.Popen",
                side_effect=OSError("synthetic start failure"),
            ):
                result = execute_action(manifest, "status", {})
            self.assertEqual(result.receipt["execution"]["outcome"], "ERROR")
            self.assertTrue(result.receipt_path and result.receipt_path.is_file())
            self.assertIn(
                "could not start",
                " ".join(result.receipt["result"]["warnings"]).lower(),
            )


if __name__ == "__main__":
    unittest.main()
