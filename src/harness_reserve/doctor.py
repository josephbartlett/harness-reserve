from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
from typing import Any

from .git_state import get_git_state, is_path_ignored
from .manifest import LoadedManifest
from .util import relative_posix, resolve_inside


def _runner_available(runner: str) -> tuple[bool, str]:
    if runner == "python":
        return True, sys.executable
    if runner == "powershell":
        value = shutil.which("pwsh.exe") or shutil.which("pwsh")
        return bool(value), value or "PowerShell 7 was not found"
    if runner == "executable":
        return True, "Entrypoint existence is validated separately"
    return False, f"Unknown runner {runner!r}"


def run_doctor(manifest: LoadedManifest) -> dict[str, Any]:
    runners = {}
    for action_id, action in manifest.actions.items():
        available, detail = _runner_available(action["runner"])
        runners[action_id] = {
            "runner": action["runner"],
            "available": available,
            "detail": detail,
            "entrypoint": action["entrypoint"],
        }
    platforms = manifest.project.get("platforms", [])
    current_platform = (
        "windows" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux"
    )
    state_ignored = is_path_ignored(
        manifest.project_root, manifest.state_directory
    )
    candidate_directory = resolve_inside(
        manifest.project_root,
        ".harness-reserve/candidates",
        label="candidate directory",
    )
    candidates_ignored = is_path_ignored(
        manifest.project_root, candidate_directory
    )
    git_state = get_git_state(manifest.project_root)
    warnings = []
    if current_platform not in platforms:
        warnings.append(
            f"Current platform {current_platform!r} is not declared by the project."
        )
    unavailable = [name for name, info in runners.items() if not info["available"]]
    if unavailable:
        warnings.append("Unavailable action runners: " + ", ".join(unavailable))
    if state_ignored is False:
        warnings.append(
            f"State directory {relative_posix(manifest.state_directory, manifest.project_root)!r} is not ignored by Git."
        )
    if candidates_ignored is False:
        warnings.append(
            "Candidate directory '.harness-reserve/candidates' is not ignored by Git."
        )
    if (
        git_state.get("is_repository")
        and git_state.get("project_root_matches_repository") is False
    ):
        warnings.append(
            "The project root is nested inside a different Git repository; "
            "repository dirty counts are unavailable."
        )
    return {
        "contract_version": 1,
        "project": {
            "id": manifest.project_id,
            "display_name": manifest.display_name,
            "root": str(manifest.project_root),
            "platforms": platforms,
        },
        "current_platform": current_platform,
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "supported": sys.version_info >= (3, 11),
        },
        "manifest": {
            "path": str(manifest.manifest_path),
            "valid": True,
            "action_count": len(manifest.actions),
        },
        "state": {
            "directory": relative_posix(manifest.state_directory, manifest.project_root),
            "ignored_by_git": state_ignored,
            "candidate_directory": relative_posix(
                candidate_directory, manifest.project_root
            ),
            "candidates_ignored_by_git": candidates_ignored,
        },
        "git": git_state,
        "runners": runners,
        "warnings": warnings,
        "ok": (
            sys.version_info >= (3, 11)
            and not unavailable
            and state_ignored is not False
            and candidates_ignored is not False
        ),
    }
