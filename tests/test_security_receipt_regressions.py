from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from harness_reserve.errors import ManifestError
from harness_reserve.receipts import load_latest
from harness_reserve.runner import execute_action
from harness_reserve.util import relative_posix, sha256_file

from support import copied_example, load_example, read_manifest, write_manifest


def _python_action(entrypoint: str) -> dict[str, object]:
    return {
        "description": "Synthetic integrity regression action.",
        "runner": "python",
        "entrypoint": entrypoint,
        "working_directory": ".",
        "fixed_args": [],
        "parameters": {},
        "environment": {},
        "timeout_seconds": 30,
        "authority": {
            "filesystem": "read-only",
            "network": "none",
            "git": "none",
            "external_systems": "none",
            "secrets": "none",
            "semantic_authority": "none",
        },
        "confirmation": {"mode": "none", "prompt": "Synthetic test only."},
        "model_invocable": False,
    }


class PreExecutionIntegrityTests(unittest.TestCase):
    def test_self_deleted_entrypoint_still_produces_error_receipt_with_pre_hash(
        self,
    ) -> None:
        with copied_example() as root:
            action_path = root / ".harness-reserve" / "actions" / "self_delete.py"
            action_path.write_text(
                "from pathlib import Path\n"
                "Path(__file__).unlink()\n",
                encoding="utf-8",
            )
            manifest_path = root / ".harness-reserve" / "operator.json"
            value = read_manifest(root)
            value["actions"]["self-delete"] = _python_action(
                ".harness-reserve/actions/self_delete.py"
            )
            write_manifest(root, value)
            expected_manifest_hash = sha256_file(manifest_path)
            expected_entrypoint_hash = sha256_file(action_path)

            result = execute_action(load_example(root), "self-delete", {})

            self.assertEqual(result.receipt["execution"]["outcome"], "ERROR")
            self.assertTrue(result.receipt_path and result.receipt_path.is_file())
            self.assertEqual(
                result.receipt["integrity"]["manifest_sha256"],
                expected_manifest_hash,
            )
            self.assertEqual(
                result.receipt["integrity"]["entrypoint_sha256"],
                expected_entrypoint_hash,
            )

    def test_self_changed_entrypoint_still_produces_error_receipt_with_pre_hash(
        self,
    ) -> None:
        with copied_example() as root:
            action_path = root / ".harness-reserve" / "actions" / "self_change.py"
            action_path.write_text(
                "from pathlib import Path\n"
                "Path(__file__).write_text("
                "\"print('replacement')\\\\n\", encoding='utf-8')\n",
                encoding="utf-8",
            )
            manifest_path = root / ".harness-reserve" / "operator.json"
            value = read_manifest(root)
            value["actions"]["self-change"] = _python_action(
                ".harness-reserve/actions/self_change.py"
            )
            write_manifest(root, value)
            expected_manifest_hash = sha256_file(manifest_path)
            expected_entrypoint_hash = sha256_file(action_path)

            result = execute_action(load_example(root), "self-change", {})

            self.assertEqual(result.receipt["execution"]["outcome"], "ERROR")
            self.assertTrue(result.receipt_path and result.receipt_path.is_file())
            self.assertEqual(
                result.receipt["integrity"]["manifest_sha256"],
                expected_manifest_hash,
            )
            self.assertEqual(
                result.receipt["integrity"]["entrypoint_sha256"],
                expected_entrypoint_hash,
            )
            self.assertNotEqual(sha256_file(action_path), expected_entrypoint_hash)


class LatestPointerIntegrityTests(unittest.TestCase):
    def test_latest_pointer_uses_minimal_digest_bound_shape(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            execute_action(manifest, "status", {})
            pointer = self._read_pointer(manifest.state_directory / "latest.json")
            self.assertEqual(
                set(pointer),
                {
                    "contract_version",
                    "run_id",
                    "receipt_path",
                    "receipt_sha256",
                },
            )
            self.assertRegex(pointer["receipt_sha256"], r"^[0-9a-f]{64}$")

    def test_latest_rejects_pointer_field_digest_run_and_path_tampering(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            execute_action(manifest, "status", {})
            latest_path = manifest.state_directory / "latest.json"
            original = self._read_pointer(latest_path)
            receipt_path = manifest.project_root.joinpath(
                *str(original["receipt_path"]).split("/")
            )

            mutations = {
                "unknown field": {**original, "unexpected": True},
                "boolean version": {**original, "contract_version": True},
                "digest": {**original, "receipt_sha256": "0" * 64},
                "run id": {**original, "run_id": "foreign-run"},
                "path traversal": {
                    **original,
                    "receipt_path": "../outside/receipt.json",
                },
            }
            for label, mutated in mutations.items():
                with self.subTest(label=label):
                    self._write_json(latest_path, mutated)
                    with self.assertRaises(ManifestError):
                        load_latest(manifest)
                    self._write_json(latest_path, original)

            alternate_path = receipt_path.with_name("alternate-receipt.json")
            alternate_path.write_bytes(receipt_path.read_bytes())
            alternate = {
                **original,
                "receipt_path": relative_posix(
                    alternate_path,
                    manifest.project_root,
                ),
                "receipt_sha256": sha256_file(alternate_path),
            }
            self._write_json(latest_path, alternate)
            with self.assertRaises(ManifestError):
                load_latest(manifest)

    def test_latest_rejects_receipt_project_and_run_identity_tampering(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            execute_action(manifest, "status", {})
            latest_path = manifest.state_directory / "latest.json"
            pointer = self._read_pointer(latest_path)
            receipt_path = manifest.project_root.joinpath(
                *str(pointer["receipt_path"]).split("/")
            )
            original_receipt = self._read_pointer(receipt_path)

            project_tamper = copy.deepcopy(original_receipt)
            project_tamper["project"]["id"] = "foreign-project"
            self._assert_receipt_tamper_rejected(
                manifest,
                latest_path,
                receipt_path,
                pointer,
                project_tamper,
            )

            run_tamper = copy.deepcopy(original_receipt)
            run_tamper["run_id"] = "foreign-run"
            self._assert_receipt_tamper_rejected(
                manifest,
                latest_path,
                receipt_path,
                pointer,
                run_tamper,
            )

    def test_latest_rejects_traversing_run_id_even_when_path_and_digest_match(
        self,
    ) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            execute_action(manifest, "status", {})
            latest_path = manifest.state_directory / "latest.json"
            pointer = self._read_pointer(latest_path)
            original_path = manifest.project_root.joinpath(
                *str(pointer["receipt_path"]).split("/")
            )
            receipt = self._read_pointer(original_path)

            malicious_run_id = "../alternate"
            receipt["run_id"] = malicious_run_id
            alternate_path = (
                manifest.state_directory / "alternate" / "receipt.json"
            )
            alternate_path.parent.mkdir(parents=True)
            self._write_json(alternate_path, receipt)
            malicious_pointer = {
                "contract_version": 1,
                "run_id": malicious_run_id,
                "receipt_path": relative_posix(
                    alternate_path,
                    manifest.project_root,
                ),
                "receipt_sha256": sha256_file(alternate_path),
            }
            self._write_json(latest_path, malicious_pointer)

            with self.assertRaises(ManifestError):
                load_latest(manifest)

    def test_latest_rejects_schema_invalid_parameters_warnings_and_integrity(
        self,
    ) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            execute_action(manifest, "status", {})
            latest_path = manifest.state_directory / "latest.json"
            pointer = self._read_pointer(latest_path)
            receipt_path = manifest.project_root.joinpath(
                *str(pointer["receipt_path"]).split("/")
            )
            original = self._read_pointer(receipt_path)

            mutations = []
            bad_parameters = copy.deepcopy(original)
            bad_parameters["invocation"]["parameters"] = {"bad/name": []}
            mutations.append(bad_parameters)
            long_warning = copy.deepcopy(original)
            long_warning["result"]["warnings"] = ["X" * 1001]
            mutations.append(long_warning)
            empty_next = copy.deepcopy(original)
            empty_next["result"]["next_action"] = ""
            mutations.append(empty_next)
            false_integrity = copy.deepcopy(original)
            false_integrity["integrity"]["manifest_changed"] = not false_integrity[
                "integrity"
            ]["manifest_changed"]
            mutations.append(false_integrity)
            boolean_version = copy.deepcopy(original)
            boolean_version["contract_version"] = True
            mutations.append(boolean_version)

            for index, mutation in enumerate(mutations):
                with self.subTest(index=index):
                    self._assert_receipt_tamper_rejected(
                        manifest,
                        latest_path,
                        receipt_path,
                        pointer,
                        mutation,
                    )

    def _assert_receipt_tamper_rejected(
        self,
        manifest,
        latest_path: Path,
        receipt_path: Path,
        pointer: dict[str, object],
        tampered_receipt: dict[str, object],
    ) -> None:
        self._write_json(receipt_path, tampered_receipt)
        tampered_pointer = {
            **pointer,
            "receipt_sha256": sha256_file(receipt_path),
        }
        self._write_json(latest_path, tampered_pointer)
        with self.assertRaises(ManifestError):
            load_latest(manifest)

    def _read_pointer(self, path: Path) -> dict[str, object]:
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def _write_json(self, path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
