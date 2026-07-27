from __future__ import annotations

import json
from pathlib import Path
import stat
from typing import Any

from .errors import ReserveError
from .util import resolve_inside, safe_id


def _template_root() -> Path:
    candidate = (
        Path(__file__).resolve().parent
        / "resources"
        / "project-adapter"
    )
    if candidate.is_dir():
        return candidate
    raise ReserveError(
        "The packaged project adapter template was not found. "
        "Reinstall Harness Reserve from a complete distribution."
    )


def _is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(
            path.stat(follow_symlinks=False), "st_file_attributes", 0
        )
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _assert_plain_ancestors(project_root: Path, destination: Path) -> None:
    current = destination.parent
    while current != project_root:
        if not current.is_relative_to(project_root):
            raise ReserveError(
                f"BLOCK: Adapter destination escapes the target project: {destination}"
            )
        if _is_reparse_or_symlink(current):
            raise ReserveError(
                "BLOCK: Adapter initialization refuses a symlink or reparse-point "
                f"ancestor: {current}"
            )
        current = current.parent


def _render_template(
    source_path: Path,
    relative: Path,
    *,
    project_id: str,
    display_name: str,
) -> tuple[str | None, bytes | None]:
    data = source_path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, data

    text = text.replace("__PROJECT_ID__", project_id)
    if relative.as_posix() == ".harness-reserve/operator.json":
        escaped_display_name = json.dumps(
            display_name, ensure_ascii=False
        )[1:-1]
        text = text.replace("__DISPLAY_NAME__", escaped_display_name)
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            raise ReserveError(
                f"Generated operator manifest would be invalid JSON: {exc}"
            ) from exc
    else:
        text = text.replace("__DISPLAY_NAME__", display_name)
    return text, None


def _create_parent_directories(
    project_root: Path,
    parent: Path,
    created_directories: list[Path],
) -> None:
    missing: list[Path] = []
    current = parent
    while current != project_root and not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(exist_ok=False)
        created_directories.append(directory)


def initialize_adapter(
    target: Path,
    *,
    project_id: str,
    display_name: str,
) -> dict[str, Any]:
    safe_id(project_id, label="project id")
    if not isinstance(display_name, str) or not display_name.strip():
        raise ReserveError("Display name must not be empty.")
    if any(character in display_name for character in "\r\n\x00"):
        raise ReserveError("Display name must be one line and contain no nulls.")

    project_root = target.expanduser().resolve()
    if not project_root.is_dir():
        raise ReserveError(f"Target project directory does not exist: {project_root}")
    source = _template_root()
    planned: list[tuple[Path, Path, Path, str | None, bytes | None]] = []
    for source_path in sorted(source.rglob("*")):
        if source_path.is_dir():
            continue
        relative = source_path.relative_to(source)
        destination = project_root / relative
        resolve_inside(project_root, relative.as_posix(), label="adapter destination")
        _assert_plain_ancestors(project_root, destination)
        if destination.exists() or _is_reparse_or_symlink(destination):
            raise ReserveError(
                f"BLOCK: Adapter initialization would overwrite existing file: {destination}"
            )
        text, binary = _render_template(
            source_path,
            relative,
            project_id=project_id,
            display_name=display_name,
        )
        planned.append((source_path, relative, destination, text, binary))

    created_paths: list[Path] = []
    created_directories: list[Path] = []
    try:
        for _, relative, destination, text, binary in planned:
            _assert_plain_ancestors(project_root, destination)
            _create_parent_directories(
                project_root, destination.parent, created_directories
            )
            _assert_plain_ancestors(project_root, destination)
            if destination.exists() or _is_reparse_or_symlink(destination):
                raise ReserveError(
                    "BLOCK: Adapter destination appeared during initialization: "
                    f"{destination}"
                )
            resolved = resolve_inside(
                project_root, relative.as_posix(), label="adapter destination"
            )
            if resolved != destination.resolve(strict=False):
                raise ReserveError(
                    f"BLOCK: Adapter destination changed during initialization: {destination}"
                )
            if text is not None:
                with destination.open(
                    "x", encoding="utf-8", newline="\n"
                ) as handle:
                    handle.write(text)
            else:
                with destination.open("xb") as handle:
                    handle.write(binary or b"")
            created_paths.append(destination)
    except Exception:
        for path in reversed(created_paths):
            path.unlink(missing_ok=True)
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise

    created = [
        destination.relative_to(project_root).as_posix()
        for destination in created_paths
    ]
    return {
        "contract_version": 1,
        "project_root": str(project_root),
        "project_id": project_id,
        "created": created,
        "next_steps": [
            "Review .harness-reserve/operator.json.",
            "Replace fail-closed action stubs with delegation to existing project scripts.",
            "Merge .harness-reserve/gitignore.append into the project .gitignore.",
            "Keep the installed harness-reserve command on PATH, set HARNESS_RESERVE_HOME, or place a checkout in a supported location.",
            "Run harness.cmd status, then validate and doctor through the shared runtime.",
        ],
    }
