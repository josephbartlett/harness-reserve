from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from harness_reserve.action_result import load_action_result
from harness_reserve.errors import ManifestError


class ActionResultContractTests(unittest.TestCase):
    def _write(self, root: Path, value: dict) -> Path:
        path = root / "action-result.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def _base(self) -> dict:
        return {
            "contract_version": 1,
            "outcome": "PASS",
            "safe_summary": "Synthetic aggregate.",
            "project_state": "READY",
            "warnings": [],
            "evidence": [],
            "next_action": None,
        }

    def test_unknown_action_result_and_evidence_fields_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            top = self._base()
            top["unexpected"] = True
            with self.assertRaises(ManifestError):
                load_action_result(self._write(root, top), project_root=root)

            evidence = self._base()
            evidence["evidence"] = [
                {
                    "kind": "proof",
                    "label": "Synthetic proof",
                    "safe_to_share": True,
                    "unexpected": True,
                }
            ]
            with self.assertRaises(ManifestError):
                load_action_result(self._write(root, evidence), project_root=root)

    def test_boolean_contract_version_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self._base()
            value["contract_version"] = True
            with self.assertRaises(ManifestError):
                load_action_result(self._write(root, value), project_root=root)

    def test_evidence_paths_and_hashes_are_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path_value, digest in [
                ("C:\\private\\proof.txt", "0" * 64),
                ("../proof.txt", "0" * 64),
                ("proof.txt", "ABC"),
            ]:
                value = self._base()
                value["evidence"] = [
                    {
                        "kind": "proof",
                        "label": "Synthetic proof",
                        "path": path_value,
                        "sha256": digest,
                        "safe_to_share": True,
                    }
                ]
                with self.subTest(path=path_value, digest=digest):
                    with self.assertRaises(ManifestError):
                        load_action_result(
                            self._write(root, value),
                            project_root=root,
                        )


if __name__ == "__main__":
    unittest.main()
