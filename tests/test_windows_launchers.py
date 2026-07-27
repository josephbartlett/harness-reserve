from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from harness_reserve.init_project import initialize_adapter

from support import REPOSITORY_ROOT, copied_example


PWSH = shutil.which("pwsh.exe") or shutil.which("pwsh")
WINDOWS_NATIVE = os.name == "nt" and PWSH is not None


def _powershell_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _copy_without_metadata(source: str, destination: str) -> str:
    Path(destination).write_bytes(Path(source).read_bytes())
    return destination


def _run_powershell_file(
    path: Path,
    *arguments: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    assert PWSH is not None
    return subprocess.run(
        [
            PWSH,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(path),
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def _run_batch(
    path: Path,
    *arguments: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(path), *arguments],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


class WindowsLauncherStaticTests(unittest.TestCase):
    def test_root_powershell_uses_isolated_utf8_no_bytecode_bridge(self) -> None:
        text = (REPOSITORY_ROOT / "reserve.ps1").read_text(encoding="utf-8")
        self.assertIn("-X utf8 -I -B -c", text)
        self.assertIn("run_module('harness_reserve.ps_bridge'", text)

    def test_batch_launchers_never_forward_percent_star(self) -> None:
        for path in REPOSITORY_ROOT.rglob("*.cmd"):
            with self.subTest(path=path.relative_to(REPOSITORY_ROOT)):
                self.assertNotIn("%*", path.read_text(encoding="utf-8"))

    def test_root_batch_launcher_is_fail_closed(self) -> None:
        text = (REPOSITORY_ROOT / "reserve.cmd").read_text(encoding="utf-8")
        self.assertIn("BLOCK:", text)
        self.assertIn("PowerShell 7", text)
        self.assertNotIn("-m harness_reserve", text)

    def test_project_batch_launchers_have_only_fixed_actions(self) -> None:
        paths = [
            REPOSITORY_ROOT
            / "src"
            / "harness_reserve"
            / "resources"
            / "project-adapter"
            / "harness.cmd",
            REPOSITORY_ROOT / "examples" / "minimal-python-project" / "harness.cmd",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(REPOSITORY_ROOT)):
                self.assertIn('set "PROJECT_ROOT=%%~fI"', text)
                self.assertIn("pwsh.exe", text)
                for action in ("use", "status", "process", "verify"):
                    self.assertIn(f'harness.ps1" {action}', text)
                self.assertNotIn("reserve.cmd", text)

    def test_generated_powershell_wrapper_supports_installed_application(self) -> None:
        path = (
            REPOSITORY_ROOT
            / "src"
            / "harness_reserve"
            / "resources"
            / "project-adapter"
            / "harness.ps1"
        )
        text = path.read_text(encoding="utf-8")
        self.assertIn("-CommandType Application", text)
        self.assertIn('"harness-reserve.exe", "harness-reserve"', text)
        self.assertIn("& $installed.Path @reserveArguments", text)


@unittest.skipUnless(WINDOWS_NATIVE, "requires native Windows and PowerShell 7")
class WindowsLauncherNativeTests(unittest.TestCase):
    def test_root_batch_launcher_blocks_instead_of_forwarding(self) -> None:
        completed = _run_batch(REPOSITORY_ROOT / "reserve.cmd", "--version")
        self.assertEqual(completed.returncode, 20)
        self.assertIn("PowerShell 7", completed.stderr)

    def test_generated_batch_launcher_exposes_only_fixed_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "Project With Spaces"
            root.mkdir()
            initialize_adapter(
                root,
                project_id="windows-launcher-probe",
                display_name="Windows Launcher Probe",
            )
            runtime = Path(temporary) / "Runtime Checkout"
            runtime.mkdir()
            (runtime / "reserve.ps1").write_text(
                (REPOSITORY_ROOT / "reserve.ps1").read_text(encoding="utf-8"),
                encoding="utf-8",
                newline="\n",
            )
            shutil.copytree(REPOSITORY_ROOT / "src", runtime / "src")
            environment = os.environ.copy()
            environment["HARNESS_RESERVE_HOME"] = str(runtime)
            harness = root / "harness.cmd"

            expected = {
                (): 10,
                ("status",): 10,
                (r".\status",): 10,
                (str(root / ".harness-reserve" / "cmd-actions" / "status"),): 10,
                ("use",): 20,
                ("process",): 20,
                ("verify",): 20,
                ("unknown",): 20,
                ("status", "extra"): 20,
            }
            for arguments, exit_code in expected.items():
                with self.subTest(arguments=arguments):
                    completed = _run_batch(harness, *arguments, env=environment)
                    self.assertEqual(
                        completed.returncode,
                        exit_code,
                        msg=completed.stdout + completed.stderr,
                    )

            for action in ("use", "status", "process", "verify"):
                marker = root / ".harness-reserve" / "cmd-actions" / action
                external = Path(temporary) / f"external-{action}.bin"
                external.write_bytes(marker.read_bytes())
                with self.subTest(same_size_external=action):
                    completed = _run_batch(
                        harness,
                        str(external),
                        env=environment,
                    )
                    self.assertEqual(
                        completed.returncode,
                        20,
                        msg=completed.stdout + completed.stderr,
                    )

            hardlink = Path(temporary) / "external-status-hardlink"
            try:
                os.link(
                    root / ".harness-reserve" / "cmd-actions" / "status",
                    hardlink,
                )
            except OSError:
                pass
            else:
                completed = _run_batch(
                    harness,
                    str(hardlink),
                    env=environment,
                )
                self.assertEqual(
                    completed.returncode,
                    20,
                    msg=completed.stdout + completed.stderr,
                )

            latest = json.loads(
                (root / ".harness-reserve" / "state" / "latest.json").read_text(
                    encoding="utf-8"
                )
            )
            receipt = json.loads(
                (root / latest["receipt_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["result"]["project_state"], "UNCONFIGURED")

    def test_example_batch_launcher_exposes_fixed_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "Runtime Root"
            repository.mkdir()
            _copy_without_metadata(
                str(REPOSITORY_ROOT / "reserve.ps1"),
                str(repository / "reserve.ps1"),
            )
            shutil.copytree(
                REPOSITORY_ROOT / "src",
                repository / "src",
                copy_function=_copy_without_metadata,
            )
            example = repository / "examples" / "minimal-python-project"
            example.parent.mkdir(parents=True)
            shutil.copytree(
                REPOSITORY_ROOT / "examples" / "minimal-python-project",
                example,
                copy_function=_copy_without_metadata,
                ignore=shutil.ignore_patterns("__pycache__", "state"),
            )

            harness = example / "harness.cmd"
            expected = {
                (): 0,
                ("status",): 0,
                (r".\status",): 0,
                (
                    str(
                        example
                        / ".harness-reserve"
                        / "cmd-actions"
                        / "status"
                    ),
                ): 0,
                ("use",): 0,
                ("process",): 0,
                ("verify",): 0,
                ("unknown",): 20,
                ("status", "extra"): 20,
            }
            for arguments, exit_code in expected.items():
                with self.subTest(arguments=arguments):
                    completed = _run_batch(harness, *arguments)
                    self.assertEqual(
                        completed.returncode,
                        exit_code,
                        msg=completed.stdout + completed.stderr,
                    )

            for action in ("use", "status", "process", "verify"):
                marker = example / ".harness-reserve" / "cmd-actions" / action
                external = repository / f"external-{action}.bin"
                external.write_bytes(marker.read_bytes())
                with self.subTest(same_size_external=action):
                    completed = _run_batch(harness, str(external))
                    self.assertEqual(
                        completed.returncode,
                        20,
                        msg=completed.stdout + completed.stderr,
                    )

    def test_powershell_bridge_ignores_native_profile_modes_and_restores_pythonpath(
        self,
    ) -> None:
        with copied_example() as root:
            reserve = REPOSITORY_ROOT / "reserve.ps1"
            parameter_json = json.dumps(
                {"item": "windows-bridge", "open-after": True},
                separators=(",", ":"),
            )
            command = "\n".join(
                [
                    "$PSNativeCommandUseErrorActionPreference = $true",
                    "$PSNativeCommandArgumentPassing = 'Legacy'",
                    "$env:PYTHONPATH = 'windows-launcher-sentinel'",
                    (
                        f"& {_powershell_literal(reserve)} "
                        f"--project-root {_powershell_literal(root)} run process "
                        f"--params-json {_powershell_literal(parameter_json)}"
                    ),
                    "$code = $LASTEXITCODE",
                    (
                        "if ($env:PYTHONPATH -ne 'windows-launcher-sentinel') "
                        "{ [Console]::Error.WriteLine('PYTHONPATH was not restored.'); exit 97 }"
                    ),
                    "exit $code",
                ]
            )
            completed = subprocess.run(
                [
                    PWSH,
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=completed.stdout + completed.stderr,
            )
            self.assertIn("PASS: processed windows-bridge", completed.stdout)

    def test_powershell_bridge_cannot_be_shadowed_by_caller_project(self) -> None:
        with copied_example() as root:
            marker = root / "shadow-imported.txt"
            shadow = root / "harness_reserve"
            shadow.mkdir()
            (shadow / "__init__.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('shadowed', encoding='utf-8')\n"
                "raise RuntimeError('caller shadow package was imported')\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    PWSH,
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(REPOSITORY_ROOT / "reserve.ps1"),
                    "--project-root",
                    str(root),
                    "validate",
                ],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=completed.stdout + completed.stderr,
            )
            self.assertFalse(marker.exists())

    def test_powershell_bridge_preserves_unicode_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "Project Ω"
            target.mkdir()
            completed = _run_powershell_file(
                REPOSITORY_ROOT / "reserve.ps1",
                "init",
                "--target",
                str(target),
                "--project-id",
                "unicode-bridge-probe",
                "--display-name",
                "Unicode Ω Probe",
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=completed.stdout + completed.stderr,
            )
            manifest = json.loads(
                (target / ".harness-reserve" / "operator.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["project"]["display_name"], "Unicode Ω Probe")

    def test_missing_runtime_from_project_powershell_wrapper_returns_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "Isolated Parent"
            root = parent / "Project"
            root.mkdir(parents=True)
            initialize_adapter(
                root,
                project_id="missing-runtime-probe",
                display_name="Missing Runtime Probe",
            )
            environment = os.environ.copy()
            environment.pop("HARNESS_RESERVE_HOME", None)
            environment["PATH"] = str(Path(PWSH).parent)
            completed = _run_powershell_file(
                root / "harness.ps1",
                "status",
                env=environment,
            )
            self.assertEqual(completed.returncode, 20)
            self.assertIn("Harness Reserve was not found", completed.stderr)

    def test_installer_creates_working_utf8_powershell_shim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            unicode_checkout = temporary_root / "Runtime Ω"
            unicode_checkout.mkdir()
            shutil.copy2(REPOSITORY_ROOT / "reserve.ps1", unicode_checkout)
            shutil.copytree(REPOSITORY_ROOT / "src", unicode_checkout / "src")

            local_app_data = temporary_root / "Local App Data"
            environment = os.environ.copy()
            environment["LOCALAPPDATA"] = str(local_app_data)
            completed = _run_powershell_file(
                REPOSITORY_ROOT / "scripts" / "Install-HarnessReserve.ps1",
                "-RepositoryRoot",
                str(unicode_checkout),
                "-CreateUserShim",
                env=environment,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=completed.stdout + completed.stderr,
            )

            shim = local_app_data / "HarnessReserve" / "bin" / "reserve.ps1"
            self.assertTrue(shim.is_file())
            content = shim.read_text(encoding="utf-8")
            self.assertIn("Runtime Ω", content)
            self.assertNotIn("Runtime ?", content)

            shim_result = _run_powershell_file(shim, "--version", env=environment)
            self.assertEqual(
                shim_result.returncode,
                0,
                msg=shim_result.stdout + shim_result.stderr,
            )


if __name__ == "__main__":
    unittest.main()
