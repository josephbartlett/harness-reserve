from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .constants import ALLOWED_OUTCOMES, ALLOWED_PROJECT_STATES, CONTRACT_VERSION
from .errors import ManifestError
from .util import load_json, relative_posix, resolve_inside

_ALLOWED_KEYS = {
    "contract_version",
    "outcome",
    "safe_summary",
    "project_state",
    "warnings",
    "evidence",
    "next_action",
    "extensions",
}
_EVIDENCE_KEYS = {"kind", "label", "path", "sha256", "safe_to_share"}
_OUTCOME_RANK = {"PASS": 0, "DEGRADED": 1, "BLOCK": 2, "ERROR": 3}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def outcome_from_exit_code(exit_code: int, *, timed_out: bool = False) -> str:
    if timed_out:
        return "ERROR"
    if exit_code == 0:
        return "PASS"
    if exit_code == 10:
        return "DEGRADED"
    if exit_code == 20:
        return "BLOCK"
    return "ERROR"


def conservative_outcome(first: str, second: str) -> str:
    return first if _OUTCOME_RANK[first] >= _OUTCOME_RANK[second] else second


def _validate_evidence(
    value: Any, label: str, *, project_root: Path | None
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be an object.")
    unknown = sorted(set(value) - _EVIDENCE_KEYS)
    if unknown:
        raise ManifestError(f"{label} has unknown fields.")
    for required in ("kind", "label", "safe_to_share"):
        if required not in value:
            raise ManifestError(f"{label}.{required} is required.")
    if not isinstance(value["kind"], str) or not value["kind"].strip():
        raise ManifestError(f"{label}.kind must be a non-empty string.")
    if not isinstance(value["label"], str) or not value["label"].strip():
        raise ManifestError(f"{label}.label must be a non-empty string.")
    if not isinstance(value["safe_to_share"], bool):
        raise ManifestError(f"{label}.safe_to_share must be boolean.")
    normalized = dict(value)
    if "path" in value:
        if not isinstance(value["path"], str):
            raise ManifestError(f"{label}.path must be a string.")
        if project_root is not None:
            evidence_path = resolve_inside(
                project_root, value["path"], label=f"{label}.path"
            )
            normalized["path"] = relative_posix(evidence_path, project_root)
    if "sha256" in value and (
        not isinstance(value["sha256"], str)
        or not _SHA256_RE.fullmatch(value["sha256"])
    ):
        raise ManifestError(f"{label}.sha256 must be 64 lowercase hexadecimal characters.")
    return normalized


def load_action_result(
    path: Path, *, project_root: Path | None = None
) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = load_json(path)
    if not isinstance(value, dict):
        raise ManifestError("Action result must be a JSON object.")
    unknown = sorted(set(value) - _ALLOWED_KEYS)
    if unknown:
        raise ManifestError("Action result has unknown fields.")
    if "extensions" in value and not isinstance(value["extensions"], dict):
        raise ManifestError("Action result extensions must be an object.")
    if (
        type(value.get("contract_version")) is not int
        or value["contract_version"] != CONTRACT_VERSION
    ):
        raise ManifestError(
            f"Action result contract_version must be {CONTRACT_VERSION}."
        )
    outcome = value.get("outcome")
    if outcome not in ALLOWED_OUTCOMES:
        raise ManifestError(f"Action result outcome must be one of {sorted(ALLOWED_OUTCOMES)}.")
    summary = value.get("safe_summary")
    if summary is not None and (not isinstance(summary, str) or len(summary) > 1000):
        raise ManifestError("Action result safe_summary must be a string up to 1000 characters.")
    state = value.get("project_state", "UNKNOWN")
    if state not in ALLOWED_PROJECT_STATES:
        raise ManifestError(
            f"Action result project_state must be one of {sorted(ALLOWED_PROJECT_STATES)}."
        )
    warnings = value.get("warnings", [])
    if not isinstance(warnings, list) or not all(
        isinstance(item, str) and len(item) <= 1000 for item in warnings
    ):
        raise ManifestError("Action result warnings must be an array of short strings.")
    evidence_value = value.get("evidence", [])
    if not isinstance(evidence_value, list):
        raise ManifestError("Action result evidence must be an array.")
    evidence = [
        _validate_evidence(
            item,
            f"action result evidence[{index}]",
            project_root=project_root,
        )
        for index, item in enumerate(evidence_value)
    ]
    next_action = value.get("next_action")
    if next_action is not None and (
        not isinstance(next_action, str)
        or not next_action.strip()
        or len(next_action) > 1000
        or "\x00" in next_action
    ):
        raise ManifestError(
            "Action result next_action must be a non-empty string up to 1000 characters."
        )
    return {
        **value,
        "project_state": state,
        "warnings": warnings,
        "evidence": evidence,
    }
