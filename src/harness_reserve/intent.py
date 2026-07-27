from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import CONTRACT_VERSION
from .errors import ManifestError
from .git_state import get_git_state
from .manifest import LoadedManifest, validate_parameter_values
from .policy import assert_model_invocable
from .runner import ExecutionResult, execute_action
from .util import load_json

_ALLOWED_KEYS = {
    "contract_version",
    "project_id",
    "action",
    "parameters",
    "reason",
    "confidence",
}
_REQUIRED_KEYS = set(_ALLOWED_KEYS)


def validate_intent(value: Any, manifest: LoadedManifest) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError("Operator intent must be a JSON object.")
    unknown = sorted(set(value) - _ALLOWED_KEYS)
    if unknown:
        raise ManifestError(f"Operator intent has unknown fields: {', '.join(unknown)}.")
    missing = sorted(_REQUIRED_KEYS - set(value))
    if missing:
        raise ManifestError(
            f"Operator intent is missing required fields: {', '.join(missing)}."
        )
    if (
        type(value.get("contract_version")) is not int
        or value["contract_version"] != CONTRACT_VERSION
    ):
        raise ManifestError(
            f"Operator intent contract_version must be {CONTRACT_VERSION}."
        )
    if value.get("project_id") != manifest.project_id:
        raise ManifestError(
            f"Operator intent targets {value.get('project_id')!r}, not {manifest.project_id!r}."
        )
    action_id = value.get("action")
    if not isinstance(action_id, str):
        raise ManifestError("Operator intent action must be a string.")
    action = manifest.action(action_id)
    parameters = value["parameters"]
    if not isinstance(parameters, dict):
        raise ManifestError("Operator intent parameters must be an object.")
    resolved = validate_parameter_values(action_id, action, parameters)
    reason = value.get("reason")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ManifestError("Operator intent reason must be a short non-empty string.")
    confidence = value.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ManifestError("Operator intent confidence must be numeric.")
    if not 0 <= float(confidence) <= 1:
        raise ManifestError("Operator intent confidence must be between 0 and 1.")
    git_state = get_git_state(manifest.project_root)
    assert_model_invocable(
        action_id,
        action,
        git_dirty=bool(git_state.get("dirty_path_count")),
        forbid_when_dirty=manifest.raw["constraints"].get(
            "forbid_model_actions_when_dirty", True
        ),
        resolved_parameters=resolved,
    )
    return {
        **value,
        "parameters": resolved,
        "confidence": float(confidence),
    }


def load_intent(path: Path, manifest: LoadedManifest) -> dict[str, Any]:
    return validate_intent(load_json(path), manifest)


def dispatch_intent(
    path: Path,
    manifest: LoadedManifest,
    *,
    execute: bool,
    confirmed: bool,
    confirmation_text: str | None,
) -> ExecutionResult:
    intent = load_intent(path, manifest)
    return execute_action(
        manifest,
        intent["action"],
        intent["parameters"],
        confirmed=confirmed,
        confirmation_text=confirmation_text,
        invoked_by="local-model-intent",
        dry_run=not execute,
    )
