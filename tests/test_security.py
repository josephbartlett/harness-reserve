from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from harness_reserve.errors import ManifestError, PolicyError
from harness_reserve.intent import dispatch_intent, load_intent
from harness_reserve.runner import execute_action

from support import REPOSITORY_ROOT, copied_example, load_example


class SecurityTests(unittest.TestCase):
    def test_sensitive_authority_requires_confirmation(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            with self.assertRaises(PolicyError):
                execute_action(manifest, "serve-private", {"minutes": 5})
            result = execute_action(
                manifest,
                "serve-private",
                {"minutes": 5},
                confirmed=True,
            )
            self.assertEqual(result.receipt["execution"]["outcome"], "PASS")

    def test_local_model_cannot_select_human_only_action(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            intent = root / "intent.json"
            intent.write_text(
                json.dumps(
                    {
                        "contract_version": 1,
                        "project_id": "minimal-python-project",
                        "action": "serve-private",
                        "parameters": {"minutes": 5},
                        "reason": "User asked for private serving.",
                        "confidence": 0.9,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(PolicyError):
                load_intent(intent, manifest)

    def test_intent_dispatch_is_dry_run_by_default(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            intent = root / "intent.json"
            intent.write_text(
                json.dumps(
                    {
                        "contract_version": 1,
                        "project_id": "minimal-python-project",
                        "action": "status",
                        "parameters": {},
                        "reason": "User asked for aggregate status.",
                        "confidence": 0.99,
                    }
                ),
                encoding="utf-8",
            )
            result = dispatch_intent(
                intent,
                manifest,
                execute=False,
                confirmed=False,
                confirmation_text=None,
            )
            self.assertTrue(result.receipt["dry_run"])
            self.assertIsNone(result.receipt_path)

    def test_runtime_contains_no_shell_true_or_invoke_expression(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (REPOSITORY_ROOT / "src" / "harness_reserve").glob("*.py")
        )
        self.assertNotIn("shell=True", source)
        self.assertNotIn("Invoke-Expression", source)

    def test_intent_project_mismatch_is_rejected(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            intent = root / "intent.json"
            intent.write_text(
                json.dumps(
                    {
                        "contract_version": 1,
                        "project_id": "different-project",
                        "action": "status",
                        "parameters": {},
                        "reason": "Wrong target.",
                        "confidence": 0.8,
                    }
                ),
                encoding="utf-8",
            )
            from harness_reserve.errors import ManifestError
            with self.assertRaises(ManifestError):
                load_intent(intent, manifest)

    def test_unknown_intent_field_is_rejected(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            intent = root / "intent.json"
            intent.write_text(
                json.dumps(
                    {
                        "contract_version": 1,
                        "project_id": "minimal-python-project",
                        "action": "status",
                        "parameters": {},
                        "reason": "Attempted extra authority.",
                        "confidence": 0.8,
                        "command": "do something unsafe",
                    }
                ),
                encoding="utf-8",
            )
            from harness_reserve.errors import ManifestError
            with self.assertRaises(ManifestError):
                load_intent(intent, manifest)

    def test_boolean_intent_contract_version_is_rejected(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            intent = root / "intent.json"
            intent.write_text(
                json.dumps(
                    {
                        "contract_version": True,
                        "project_id": "minimal-python-project",
                        "action": "status",
                        "parameters": {},
                        "reason": "Synthetic invalid contract version.",
                        "confidence": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ManifestError):
                load_intent(intent, manifest)


if __name__ == "__main__":
    unittest.main()
