from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import tempfile
from typing import Any

from .errors import ManifestError

_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$")
_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_id(value: str, *, label: str = "identifier") -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ManifestError(
            f"{label} must match {_ID_RE.pattern!r}; received {value!r}."
        )
    return value


def safe_env_name(value: str) -> str:
    if not isinstance(value, str) or not _ENV_RE.fullmatch(value):
        raise ManifestError(f"Invalid environment variable name: {value!r}.")
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON object key: {key!r}.")
        value[key] = item
    return value


def _reject_nonfinite_constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON number is not allowed: {value}.")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"Non-finite JSON number is not allowed: {value}.")
    return parsed


def strict_json_loads(text: str, *, label: str = "JSON") -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
            parse_float=_parse_finite_float,
        )
    except json.JSONDecodeError as exc:
        raise ManifestError(
            f"Malformed {label}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except ValueError as exc:
        raise ManifestError(f"Malformed {label}: {exc}") from exc


def load_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ManifestError(f"Required JSON file does not exist: {path}") from exc
    return strict_json_loads(text, label=f"JSON in {path}")


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        json.dumps(
            data,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_relative_path_text(relative: str, *, label: str) -> None:
    if not isinstance(relative, str) or not relative.strip():
        raise ManifestError(f"{label} must be a non-empty repository-relative path.")
    if "\x00" in relative:
        raise ManifestError(f"{label} contains a null character.")

    windows_path = PureWindowsPath(relative)
    if windows_path.drive or windows_path.root:
        raise ManifestError(
            f"{label} must be relative and must not use a drive, share, or rooted path: "
            f"{relative!r}."
        )

    for component in windows_path.parts:
        if component == "..":
            raise ManifestError(f"{label} contains parent traversal: {relative!r}.")
        if component == ".":
            continue
        if ":" in component:
            raise ManifestError(
                f"{label} contains a colon, which is forbidden in portable repository paths: "
                f"{relative!r}."
            )
        if component.rstrip(" .") != component:
            raise ManifestError(
                f"{label} contains a Windows path component ending in a dot or space: "
                f"{relative!r}."
            )
        reserved_base = component.split(".", 1)[0].upper()
        if reserved_base in _WINDOWS_RESERVED_NAMES:
            raise ManifestError(
                f"{label} contains reserved Windows device name {component!r}."
            )


def resolve_inside(root: Path, relative: str, *, label: str) -> Path:
    validate_relative_path_text(relative, label=label)
    candidate_input = Path(relative)
    if candidate_input.is_absolute():
        raise ManifestError(f"{label} must be relative, not absolute: {relative!r}.")
    root_resolved = root.resolve()
    candidate = (root_resolved / candidate_input).resolve(strict=False)
    if not is_relative_to(candidate, root_resolved):
        raise ManifestError(f"{label} escapes the project root: {relative!r}.")
    return candidate


def relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def parse_json_argument(value: str | None) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if value.startswith("@"):
        payload = load_json(Path(value[1:]).expanduser().resolve())
    else:
        payload = strict_json_loads(value, label="--params-json value")
    if not isinstance(payload, dict):
        raise ManifestError("Action parameters must be a JSON object.")
    return payload


def parse_version(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+", value
    ):
        raise ManifestError(f"Version must use MAJOR.MINOR.PATCH: {value!r}.")
    parts = value.split(".")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]
