from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
from typing import Any


_GIT_CONTROL_ENVIRONMENT = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_CONFIG_SYSTEM",
    "GIT_DIR",
    "GIT_EXEC_PATH",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_WORK_TREE",
}


def _sanitized_git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in list(environment):
        if name in _GIT_CONTROL_ENVIRONMENT or name.startswith("GIT_CONFIG_"):
            environment.pop(name, None)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    return environment


def _run_git(root: Path, *args: str) -> str | None:
    git = shutil.which("git")
    if not git:
        return None
    try:
        completed = subprocess.run(
            [
                git,
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-C",
                str(root),
                *args,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_sanitized_git_environment(),
            timeout=15,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def get_git_state(root: Path) -> dict[str, Any]:
    root_resolved = root.resolve()
    inside = _run_git(root_resolved, "rev-parse", "--is-inside-work-tree")
    if inside != "true":
        return {
            "available": bool(shutil.which("git")),
            "is_repository": False,
            "repository_root": None,
            "project_root_matches_repository": None,
            "branch": None,
            "commit": None,
            "dirty_path_count": None,
        }
    top_level_value = _run_git(root_resolved, "rev-parse", "--show-toplevel")
    try:
        repository_root = (
            Path(top_level_value).resolve() if top_level_value is not None else None
        )
    except OSError:
        repository_root = None
    identity_matches = (
        repository_root == root_resolved if repository_root is not None else False
    )
    branch = _run_git(root_resolved, "branch", "--show-current") or None
    commit = _run_git(root_resolved, "rev-parse", "HEAD") or None
    status = (
        _run_git(root_resolved, "status", "--porcelain=v1", "-z")
        if identity_matches
        else None
    )
    dirty_count = (
        None
        if status is None
        else len([item for item in status.split("\x00") if item])
    )
    return {
        "available": True,
        "is_repository": True,
        "repository_root": str(repository_root) if repository_root else None,
        "project_root_matches_repository": identity_matches,
        "branch": branch,
        "commit": commit,
        "dirty_path_count": dirty_count,
    }


def is_path_ignored(root: Path, path: Path) -> bool | None:
    git = shutil.which("git")
    if not git:
        return None
    if _run_git(root, "rev-parse", "--is-inside-work-tree") != "true":
        return None
    # A directory-only pattern such as ".harness-reserve/state/" does not match
    # the nonexistent directory path itself. Probe a synthetic child without
    # creating it so doctor verifies the rule that will protect future state.
    ignore_probe = path.resolve(strict=False) / ".harness-reserve-ignore-probe"
    try:
        completed = subprocess.run(
            [
                git,
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-C",
                str(root.resolve()),
                "check-ignore",
                "-q",
                "--",
                str(ignore_probe),
            ],
            check=False,
            timeout=10,
            env=_sanitized_git_environment(),
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    return None
