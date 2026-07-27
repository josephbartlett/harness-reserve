from __future__ import annotations

import re
from typing import Any

from .constants import SENSITIVE_AUTHORITY
from .errors import PolicyError

_MODEL_ALLOWED = {
    "filesystem": {"read-only", "derived-only"},
    "network": {"none", "loopback"},
    "git": {"none", "read"},
    "external_systems": {"none"},
    "secrets": {"none"},
    "semantic_authority": {"none", "candidate"},
}
_MODEL_SAFE_STRING_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def is_model_safe_text(value: Any) -> bool:
    return isinstance(value, str) and bool(_MODEL_SAFE_STRING_RE.fullmatch(value))


def confirmation_reason(action: dict[str, Any]) -> str | None:
    confirmation = action["confirmation"]
    if confirmation["mode"] != "none":
        return confirmation.get("prompt", "This action requires confirmation.")
    authority = action["authority"]
    for key, value in SENSITIVE_AUTHORITY:
        if authority.get(key) == value:
            return f"Sensitive authority requires confirmation: {key}={value}."
    return None


def assert_confirmed(
    action: dict[str, Any], *, confirmed: bool, confirmation_text: str | None
) -> None:
    reason = confirmation_reason(action)
    if reason is None:
        return
    mode = action["confirmation"]["mode"]
    if mode == "phrase":
        expected = action["confirmation"]["phrase"]
        if confirmation_text != expected:
            raise PolicyError(
                f"BLOCK: {reason} Supply the exact confirmation phrase declared by the project."
            )
        return
    if not confirmed:
        raise PolicyError(f"BLOCK: {reason} Re-run with --confirm after review.")


def assert_model_invocable(
    action_id: str,
    action: dict[str, Any],
    *,
    git_dirty: bool,
    forbid_when_dirty: bool,
    resolved_parameters: dict[str, Any] | None = None,
) -> None:
    if not action.get("model_invocable", False):
        raise PolicyError(
            f"BLOCK: Action {action_id!r} is not eligible for local-model intent dispatch."
        )
    authority = action["authority"]
    violations = [
        f"{key}={authority[key]}"
        for key, allowed in _MODEL_ALLOWED.items()
        if authority.get(key) not in allowed
    ]
    if violations:
        raise PolicyError(
            "BLOCK: A local model cannot select an action with this authority: "
            + ", ".join(violations)
            + "."
        )
    sensitive = [
        name
        for name, spec in action.get("parameters", {}).items()
        if spec.get("sensitive", False)
    ]
    if sensitive:
        raise PolicyError(
            "BLOCK: A local model cannot select an action with sensitive parameters: "
            + ", ".join(sorted(sensitive))
            + "."
        )
    for name, value in (resolved_parameters or {}).items():
        spec = action.get("parameters", {}).get(name, {})
        if spec.get("type") in {"string", "enum"} and (
            not is_model_safe_text(value)
        ):
            raise PolicyError(
                "BLOCK: Model-selected textual parameters must be bounded portable tokens "
                f"without path or command syntax; parameter {name!r} was rejected."
            )
    if git_dirty and forbid_when_dirty:
        raise PolicyError(
            "BLOCK: Local-model intent dispatch is disabled while Git is dirty."
        )


def build_arguments(
    action: dict[str, Any], resolved_parameters: dict[str, Any]
) -> list[str]:
    arguments = list(action.get("fixed_args", []))
    for name, spec in action.get("parameters", {}).items():
        if name not in resolved_parameters:
            continue
        value = resolved_parameters[name]
        flag = spec["flag"]
        if spec["type"] == "boolean":
            if value:
                arguments.append(flag)
        else:
            arguments.extend([flag, str(value)])
    return arguments


def build_redacted_arguments(
    action: dict[str, Any], resolved_parameters: dict[str, Any]
) -> list[str]:
    arguments = list(action.get("fixed_args", []))
    for name, spec in action.get("parameters", {}).items():
        if name not in resolved_parameters:
            continue
        value = resolved_parameters[name]
        flag = spec["flag"]
        if spec.get("sensitive", False):
            if spec["type"] == "boolean":
                arguments.append("<redacted-argument>")
            else:
                arguments.extend([flag, "<redacted>"])
            continue
        if spec["type"] == "boolean":
            if value:
                arguments.append(flag)
        else:
            arguments.extend([flag, str(value)])
    return arguments


def redact_parameters(
    action: dict[str, Any], resolved_parameters: dict[str, Any]
) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for name, value in resolved_parameters.items():
        spec = action["parameters"][name]
        redacted[name] = "<redacted>" if spec.get("sensitive", False) else value
    return redacted
