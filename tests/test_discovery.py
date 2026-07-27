from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from harness_reserve.discovery import discover_project
from harness_reserve.errors import DiscoveryError


class DiscoveryTests(unittest.TestCase):
    def test_discovers_manifest_from_nested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            nested = root / "a" / "b"
            manifest = root / ".harness-reserve" / "operator.json"
            nested.mkdir(parents=True)
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}", encoding="utf-8")
            found_root, found_manifest = discover_project(start=nested)
            self.assertEqual(found_root, root.resolve())
            self.assertEqual(found_manifest, manifest.resolve())

    def test_missing_manifest_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(DiscoveryError):
                discover_project(project_root=Path(temporary))

    def test_explicit_manifest_outside_project_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            root.mkdir()
            manifest = base / "outside.json"
            manifest.write_text("{}", encoding="utf-8")
            with self.assertRaises(DiscoveryError):
                discover_project(project_root=root, manifest_path=manifest)


if __name__ == "__main__":
    unittest.main()
