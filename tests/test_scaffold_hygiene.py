from __future__ import annotations

from contextlib import redirect_stderr
import importlib.util
from io import StringIO
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str) -> ModuleType:
    path = REPOSITORY_ROOT / "scripts" / f"{name}.py"
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise AssertionError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class ScaffoldHygieneTests(unittest.TestCase):
    def test_attune_governance_state_is_never_scanned_or_inventoried(self) -> None:
        validator = _load_script("validate_scaffold")
        ignored = REPOSITORY_ROOT / ".attune" / "materialized" / "private.json"
        self.assertTrue(validator.excluded_from_repository_scan(ignored))

        builder = _load_script("build_scaffold_manifest")
        self.assertIn(".attune", builder.EXCLUDED_PARTS)

    def test_clean_fixture_check_detects_generated_runtime_and_cache_output(
        self,
    ) -> None:
        validator = _load_script("validate_scaffold")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generated = [
                root
                / "examples"
                / "minimal-python-project"
                / ".harness-reserve"
                / "state",
                root
                / "examples"
                / "minimal-python-project"
                / ".harness-reserve"
                / "candidates",
                root / "tests" / "__pycache__",
                root / "tests" / "probe.pyc",
            ]
            for path in generated:
                if path.suffix:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"generated")
                else:
                    path.mkdir(parents=True, exist_ok=True)

            stderr = StringIO()
            with (
                patch.object(validator, "ROOT", root),
                redirect_stderr(stderr),
                self.assertRaises(SystemExit) as caught,
            ):
                validator.validate_clean_fixture()

            self.assertEqual(caught.exception.code, 20)
            message = stderr.getvalue()
            for path in generated:
                self.assertIn(path.relative_to(root).as_posix(), message.replace("\\", "/"))

    def test_manifest_builder_ignores_common_local_build_artifacts(self) -> None:
        builder = _load_script("build_scaffold_manifest")
        for part in (".attune", ".venv", "build", "dist", "__pycache__"):
            self.assertIn(part, builder.EXCLUDED_PARTS)

    @unittest.skipUnless(shutil.which("git"), "Git is required for index hygiene")
    def test_tracked_attune_runtime_and_candidate_state_is_rejected(self) -> None:
        validator = _load_script("validate_scaffold")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(
                ["git", "-C", str(root), "init", "-q"],
                check=True,
                capture_output=True,
            )
            forbidden = [
                root / ".attune" / "binding.json",
                root
                / "example"
                / ".harness-reserve"
                / "state"
                / "receipt.json",
                root
                / "example"
                / ".harness-reserve"
                / "candidates"
                / "private.txt",
            ]
            for path in forbidden:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(root), "add", "-f", "."],
                check=True,
                capture_output=True,
            )

            stderr = StringIO()
            with (
                patch.object(validator, "ROOT", root),
                redirect_stderr(stderr),
                self.assertRaises(SystemExit) as caught,
            ):
                validator.validate_tracked_state_boundaries()

            self.assertEqual(caught.exception.code, 20)
            message = stderr.getvalue().replace("\\", "/")
            for path in forbidden:
                self.assertIn(path.relative_to(root).as_posix(), message)


if __name__ == "__main__":
    unittest.main()
