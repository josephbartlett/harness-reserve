from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from harness_reserve.discovery import discover_project
from harness_reserve.errors import DiscoveryError, ManifestError, ReserveError
from harness_reserve.init_project import initialize_adapter
from harness_reserve.manifest import load_manifest
from harness_reserve.util import load_json, resolve_inside

from support import (
    REPOSITORY_ROOT,
    copied_example,
    load_example,
    read_manifest,
    write_manifest,
)


class StrictJsonTests(unittest.TestCase):
    def test_duplicate_object_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.json"
            path.write_text(
                '{"action":"status","action":"serve-private"}',
                encoding="utf-8",
            )
            with self.assertRaises(ManifestError):
                load_json(path)

    def test_non_finite_json_numbers_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "nan.json"
            path.write_text('{"confidence":NaN}', encoding="utf-8")
            with self.assertRaises(ManifestError):
                load_json(path)

    def test_numeric_overflow_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "overflow.json"
            path.write_text('{"extensions":{"value":1e999}}', encoding="utf-8")
            with self.assertRaises(ManifestError):
                load_json(path)


class WindowsPathSafetyTests(unittest.TestCase):
    def test_windows_unsafe_relative_path_forms_are_rejected_on_every_host(self) -> None:
        unsafe = (
            r"C:drive-relative\entry.py",
            r"C:\absolute\entry.py",
            r"\\server\share\entry.py",
            r"\\?\C:\extended\entry.py",
            r"\root-relative\entry.py",
            r"actions\carrier.py:payload.py",
            r"actions\NUL",
            r"actions\CON.py",
            r"actions\aux.txt",
            r"actions\PRN",
            r"actions\COM1.log",
            r"actions\lpt9.ps1",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for value in unsafe:
                with self.subTest(value=value):
                    with self.assertRaises(ManifestError):
                        resolve_inside(root, value, label="probe")

    def test_ordinary_repository_relative_path_remains_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            resolved = resolve_inside(
                root,
                ".harness-reserve/actions/status.py",
                label="probe",
            )
            self.assertTrue(resolved.is_relative_to(root))

    @unittest.skipUnless(os.name == "nt", "NTFS alternate streams are Windows-specific")
    def test_existing_ntfs_alternate_stream_entrypoint_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            actions = root / ".harness-reserve" / "actions"
            actions.mkdir(parents=True)
            carrier = actions / "carrier.py"
            carrier.write_text("print('base')\n", encoding="utf-8")
            stream = Path(str(carrier) + ":payload.py")
            try:
                stream.write_text("print('alternate stream')\n", encoding="utf-8")
            except OSError as exc:
                self.skipTest(f"Temporary filesystem does not support NTFS ADS: {exc}")

            value = {
                "contract_version": 1,
                "project": {
                    "id": "ads-probe",
                    "display_name": "ADS Probe",
                    "platforms": ["windows"],
                },
                "default_action": "probe",
                "actions": {
                    "probe": {
                        "description": "ADS path probe.",
                        "runner": "python",
                        "entrypoint": ".harness-reserve/actions/carrier.py:payload.py",
                    }
                },
            }
            manifest_path = root / ".harness-reserve" / "operator.json"
            manifest_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ManifestError):
                load_manifest(root, manifest_path)

    def test_executable_runner_rejects_cmd_entrypoint(self) -> None:
        with copied_example() as root:
            action_path = root / ".harness-reserve" / "actions" / "unsafe.cmd"
            action_path.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
            value = read_manifest(root)
            value["actions"]["status"]["runner"] = "executable"
            value["actions"]["status"]["entrypoint"] = (
                ".harness-reserve/actions/unsafe.cmd"
            )
            write_manifest(root, value)
            with self.assertRaises(ManifestError):
                load_example(root)

    def test_executable_runner_rejects_portable_script_entrypoints(self) -> None:
        for name in ("unsafe.sh", "unsafe-no-suffix"):
            with self.subTest(name=name), copied_example() as root:
                action_path = root / ".harness-reserve" / "actions" / name
                action_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                value = read_manifest(root)
                value["actions"]["status"]["runner"] = "executable"
                value["actions"]["status"]["entrypoint"] = (
                    f".harness-reserve/actions/{name}"
                )
                write_manifest(root, value)
                with self.assertRaises(ManifestError):
                    load_example(root)

    def test_runtime_state_must_stay_under_reserved_state_root(self) -> None:
        unsafe_directories = (
            ".",
            "state",
            ".harness-reserve",
            ".harness-reserve/candidates",
            ".harness-reserve/state-sibling",
        )
        for state_directory in unsafe_directories:
            with self.subTest(state_directory=state_directory), copied_example() as root:
                value = read_manifest(root)
                value["state"]["directory"] = state_directory
                write_manifest(root, value)
                with self.assertRaises(ManifestError):
                    load_example(root)

    def test_handoff_directory_must_stay_under_runtime_state(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["state"]["handoff_directory"] = ".harness-reserve/handoffs"
            write_manifest(root, value)
            with self.assertRaises(ManifestError):
                load_example(root)

    @unittest.skipUnless(os.name == "nt", "Batch parsing regression is Windows-specific")
    def test_cmd_launchers_do_not_reexpand_environment_selector_tokens(self) -> None:
        wrappers = (
            REPOSITORY_ROOT / "reserve.cmd",
            REPOSITORY_ROOT
            / "src"
            / "harness_reserve"
            / "resources"
            / "project-adapter"
            / "harness.cmd",
            REPOSITORY_ROOT / "examples" / "minimal-python-project" / "harness.cmd",
        )
        with tempfile.TemporaryDirectory() as temporary:
            for index, wrapper in enumerate(wrappers):
                marker = Path(temporary) / f"owned-{index}.txt"
                environment = os.environ.copy()
                environment["HR_SELECTOR_INJECT"] = (
                    f'use"=="use" echo OWNED>"{marker}" & rem "'
                )
                with self.subTest(wrapper=wrapper):
                    completed = subprocess.run(
                        [str(wrapper), "%HR_SELECTOR_INJECT%"],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        env=environment,
                    )
                    self.assertEqual(completed.returncode, 20)
                    self.assertFalse(
                        marker.exists(),
                        f"{wrapper.name} interpreted an untrusted batch argument",
                    )


class ReparseAndInitializationTests(unittest.TestCase):
    def test_discovery_rejects_manifest_directory_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            outside = base / "outside-manifest"
            root.mkdir()
            outside.mkdir()
            (outside / "operator.json").write_text("{}", encoding="utf-8")
            try:
                os.symlink(
                    outside,
                    root / ".harness-reserve",
                    target_is_directory=True,
                )
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"Directory symlinks are unavailable: {exc}")

            with self.assertRaises(DiscoveryError):
                discover_project(project_root=root)

    def test_init_json_escapes_single_line_display_name(self) -> None:
        display_name = 'Quoted "name" with a \\ backslash'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_adapter(
                root,
                project_id="display-name-probe",
                display_name=display_name,
            )
            manifest = load_manifest(
                root,
                root / ".harness-reserve" / "operator.json",
            )
            self.assertEqual(manifest.display_name, display_name)

    def test_init_rejects_control_characters_without_partial_writes(self) -> None:
        for display_name in ("line one\nline two", "line one\rline two", "name\x00"):
            with self.subTest(display_name=repr(display_name)):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    with self.assertRaises(ReserveError):
                        initialize_adapter(
                            root,
                            project_id="display-name-probe",
                            display_name=display_name,
                        )
                    self.assertEqual(list(root.iterdir()), [])

    def test_init_rejects_reparse_escape_without_partial_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            outside = base / "outside-target"
            root.mkdir()
            outside.mkdir()
            try:
                os.symlink(
                    outside,
                    root / ".harness-reserve",
                    target_is_directory=True,
                )
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"Directory symlinks are unavailable: {exc}")

            with self.assertRaises(ReserveError):
                initialize_adapter(
                    root,
                    project_id="reparse-probe",
                    display_name="Reparse Probe",
                )

            self.assertEqual(list(outside.iterdir()), [])
            self.assertFalse((root / "harness.cmd").exists())
            self.assertFalse((root / "harness.ps1").exists())

    def test_init_rejects_broken_destination_symlink_without_following_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            root.mkdir()
            redirected = base / "redirected.ps1"
            destination = root / "harness.ps1"
            try:
                os.symlink(
                    redirected,
                    destination,
                    target_is_directory=False,
                )
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"File symlinks are unavailable: {exc}")

            with self.assertRaises(ReserveError):
                initialize_adapter(
                    root,
                    project_id="broken-link-probe",
                    display_name="Broken Link Probe",
                )

            self.assertTrue(destination.is_symlink())
            self.assertFalse(redirected.exists())
            self.assertFalse((root / ".harness-reserve").exists())
            self.assertFalse((root / "harness.cmd").exists())


if __name__ == "__main__":
    unittest.main()
