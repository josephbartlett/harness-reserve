from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from harness_reserve.errors import ReserveError
from harness_reserve.init_project import initialize_adapter
from harness_reserve.manifest import load_manifest


class InitTests(unittest.TestCase):
    def test_init_creates_fail_closed_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = initialize_adapter(
                root, project_id="greenfield", display_name="Greenfield"
            )
            self.assertIn("harness.cmd", result["created"])
            manifest = load_manifest(
                root,
                root / ".harness-reserve" / "operator.json",
                check_files=True,
            )
            self.assertEqual(manifest.project_id, "greenfield")
            self.assertEqual(manifest.default_action, "status")
            ignore_guidance = (
                root / ".harness-reserve" / "gitignore.append"
            ).read_text(encoding="utf-8")
            self.assertIn(".harness-reserve/state/", ignore_guidance)
            self.assertIn(".harness-reserve/candidates/", ignore_guidance)
            self.assertTrue(
                all(
                    not action["model_invocable"]
                    for action in manifest.actions.values()
                )
            )

    def test_init_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_adapter(root, project_id="greenfield", display_name="Greenfield")
            with self.assertRaises(ReserveError):
                initialize_adapter(root, project_id="greenfield", display_name="Greenfield")


if __name__ == "__main__":
    unittest.main()
