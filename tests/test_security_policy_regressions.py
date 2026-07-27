from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from harness_reserve.constants import SENSITIVE_AUTHORITY
from harness_reserve.errors import PolicyError
from harness_reserve.git_state import get_git_state
from harness_reserve.intent import load_intent
from harness_reserve.policy import assert_confirmed

from support import copied_example, load_example, read_manifest, write_manifest


def _base_authority() -> dict[str, str]:
    return {
        "filesystem": "read-only",
        "network": "none",
        "git": "none",
        "external_systems": "none",
        "secrets": "none",
        "semantic_authority": "none",
    }


def _write_intent(
    root: Path,
    *,
    action: str,
    parameters: dict[str, object],
) -> Path:
    path = root / "intent.json"
    path.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "project_id": "minimal-python-project",
                "action": action,
                "parameters": parameters,
                "reason": "Synthetic policy regression probe.",
                "confidence": 0.95,
            }
        ),
        encoding="utf-8",
    )
    return path


class ConfirmationFloorTests(unittest.TestCase):
    def test_every_sensitive_authority_has_a_hard_confirmation_floor(self) -> None:
        for key, value in sorted(SENSITIVE_AUTHORITY):
            with self.subTest(authority=f"{key}={value}"):
                authority = _base_authority()
                authority[key] = value
                action = {
                    "authority": authority,
                    "confirmation": {
                        "mode": "none",
                        "prompt": "Manifest requests no confirmation.",
                    },
                }
                with self.assertRaises(PolicyError):
                    assert_confirmed(
                        action,
                        confirmed=False,
                        confirmation_text=None,
                    )
                assert_confirmed(
                    action,
                    confirmed=True,
                    confirmation_text=None,
                )


class ModelIntentPolicyTests(unittest.TestCase):
    def test_model_authority_ceiling_blocks_actions_even_when_marked_invocable(
        self,
    ) -> None:
        forbidden = [
            ("filesystem", "workspace-write"),
            ("filesystem", "unrestricted-project"),
            ("network", "private-lan"),
            ("network", "internet"),
            ("git", "write"),
            ("git", "publish"),
            ("external_systems", "write"),
            ("secrets", "read"),
            ("semantic_authority", "canonical"),
        ]
        for dimension, authority_value in forbidden:
            with self.subTest(dimension=dimension, value=authority_value):
                with copied_example() as root:
                    value = read_manifest(root)
                    value["actions"]["status"]["model_invocable"] = True
                    value["actions"]["status"]["authority"][dimension] = authority_value
                    write_manifest(root, value)
                    intent = _write_intent(root, action="status", parameters={})
                    with self.assertRaises(PolicyError):
                        load_intent(intent, load_example(root))

    def test_model_cannot_invoke_action_declaring_sensitive_parameter(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["actions"]["status"]["parameters"] = {
                "token": {
                    "type": "string",
                    "flag": "--token",
                    "required": False,
                    "sensitive": True,
                }
            }
            write_manifest(root, value)
            manifest = load_example(root)
            intent = _write_intent(root, action="status", parameters={})

            with self.assertRaises(PolicyError):
                load_intent(intent, manifest)

    def test_model_cannot_supply_path_like_string_parameter(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["actions"]["status"]["parameters"] = {
                "target": {
                    "type": "string",
                    "flag": "--target",
                    "required": True,
                    "sensitive": False,
                }
            }
            write_manifest(root, value)
            manifest = load_example(root)
            intent = _write_intent(
                root,
                action="status",
                parameters={"target": r"..\outside\private.txt"},
            )

            with self.assertRaises(PolicyError):
                load_intent(intent, manifest)

    def test_model_cannot_select_path_like_enum_value(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["actions"]["status"]["parameters"] = {
                "target": {
                    "type": "enum",
                    "flag": "--target",
                    "required": True,
                    "sensitive": False,
                    "values": ["safe-token", r"..\outside\private.txt"],
                }
            }
            write_manifest(root, value)
            manifest = load_example(root)
            intent = _write_intent(
                root,
                action="status",
                parameters={"target": r"..\outside\private.txt"},
            )

            with self.assertRaises(PolicyError):
                load_intent(intent, manifest)

    @unittest.skipUnless(shutil.which("git"), "Git is required for dirty-worktree policy")
    def test_dirty_constraint_blocks_all_model_actions_when_enabled(self) -> None:
        with copied_example() as root:
            intent = _write_intent(root, action="status", parameters={})
            self._initialize_repository(root)
            (root / "app.py").write_text(
                (root / "app.py").read_text(encoding="utf-8") + "\n# dirty\n",
                encoding="utf-8",
            )

            value = read_manifest(root)
            value["constraints"]["forbid_model_actions_when_dirty"] = True
            write_manifest(root, value)
            manifest = load_example(root)
            with self.assertRaises(PolicyError):
                load_intent(intent, manifest)

            value = read_manifest(root)
            value["constraints"]["forbid_model_actions_when_dirty"] = False
            write_manifest(root, value)
            permitted = load_intent(intent, load_example(root))
            self.assertEqual(permitted["action"], "status")

    def _initialize_repository(self, root: Path) -> None:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "probe@example.invalid")
        self._git(root, "config", "user.name", "Harness Reserve Probe")
        self._git(root, "config", "commit.gpgsign", "false")
        self._git(root, "add", "-A")
        self._git(root, "commit", "-qm", "fixture")

    def _git(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )


@unittest.skipUnless(shutil.which("git"), "Git is required for Git-state regressions")
class GitStateSafetyTests(unittest.TestCase):
    def test_git_control_environment_cannot_redirect_repository_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            target = base / "target"
            target.mkdir()
            self._initialize_repository(target, content="ORIGINAL")
            actual_commit = get_git_state(target)["commit"]
            (target / "tracked.txt").write_text("DIRTY", encoding="utf-8")

            fake_git_dir = base / "fake.git"
            self._run(["git", "init", "--bare", "-q", str(fake_git_dir)])
            fake_environment = self._clean_git_environment()
            fake_environment.update(
                {
                    "GIT_DIR": str(fake_git_dir),
                    "GIT_WORK_TREE": str(target),
                    "GIT_AUTHOR_NAME": "Probe",
                    "GIT_AUTHOR_EMAIL": "probe@example.invalid",
                    "GIT_COMMITTER_NAME": "Probe",
                    "GIT_COMMITTER_EMAIL": "probe@example.invalid",
                }
            )
            self._run(["git", "add", "tracked.txt"], env=fake_environment)
            self._run(
                ["git", "commit", "-qm", "fake clean snapshot"],
                env=fake_environment,
            )

            with patch.dict(
                os.environ,
                {
                    "GIT_DIR": str(fake_git_dir),
                    "GIT_WORK_TREE": str(target),
                },
                clear=False,
            ):
                observed = get_git_state(target)

            self.assertTrue(observed["is_repository"])
            self.assertEqual(observed["commit"], actual_commit)
            self.assertGreater(observed["dirty_path_count"], 0)

    def test_git_status_does_not_execute_configured_fsmonitor_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            root.mkdir()
            self._initialize_repository(root, content="tracked")
            marker = base / "fsmonitor-invoked.txt"
            hook = root / ".git" / "hooks" / "probe-fsmonitor"
            hook.write_text(
                "#!/bin/sh\n"
                f'printf invoked >> "{marker.as_posix()}"\n'
                "printf '\\n'\n",
                encoding="utf-8",
            )
            try:
                hook.chmod(0o755)
            except OSError:
                pass
            self._git(root, "config", "core.fsmonitor", hook.as_posix())

            self._git(root, "status", "--porcelain=v1")
            if not marker.exists():
                self.skipTest("Installed Git does not execute configured fsmonitor hooks")
            marker.unlink()

            state = get_git_state(root)
            self.assertTrue(state["is_repository"])
            self.assertFalse(
                marker.exists(),
                "Git-state inspection executed repository-configured code",
            )

    def _initialize_repository(self, root: Path, *, content: str) -> None:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "probe@example.invalid")
        self._git(root, "config", "user.name", "Harness Reserve Probe")
        self._git(root, "config", "commit.gpgsign", "false")
        (root / "tracked.txt").write_text(content, encoding="utf-8")
        self._git(root, "add", "tracked.txt")
        self._git(root, "commit", "-qm", "fixture")

    def _git(
        self,
        root: Path,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        return self._run(["git", "-C", str(root), *args])

    def _run(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    def _clean_git_environment(self) -> dict[str, str]:
        return {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith("GIT_")
        }


if __name__ == "__main__":
    unittest.main()
