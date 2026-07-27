from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any

from .constants import (
    ALLOWED_OUTCOMES,
    ALLOWED_PROJECT_STATES,
    ALLOWED_RUNNERS,
    CONTRACT_VERSION,
)
from .errors import ManifestError
from .manifest import LoadedManifest
from .util import (
    atomic_write_json,
    load_json,
    relative_posix,
    resolve_inside,
    sha256_file,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ACTION_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$")
_RUN_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?Z$"
)
_POINTER_KEYS = {
    "contract_version",
    "run_id",
    "receipt_path",
    "receipt_sha256",
}
_RECEIPT_KEYS = {
    "contract_version",
    "runtime_version",
    "run_id",
    "timestamps",
    "project",
    "invocation",
    "authority",
    "execution",
    "integrity",
    "repository_before",
    "repository_after",
    "result",
    "privacy",
}
_TIMESTAMP_KEYS = {"started_at", "finished_at"}
_PROJECT_KEYS = {"id", "display_name", "root"}
_INVOCATION_KEYS = {"action", "invoked_by", "parameters"}
_AUTHORITY_KEYS = {
    "filesystem",
    "network",
    "git",
    "external_systems",
    "secrets",
    "semantic_authority",
}
_AUTHORITY_VALUES = {
    "filesystem": {
        "read-only",
        "derived-only",
        "workspace-write",
        "unrestricted-project",
    },
    "network": {"none", "loopback", "private-lan", "internet"},
    "git": {"none", "read", "write", "publish"},
    "external_systems": {"none", "read", "write"},
    "secrets": {"none", "read"},
    "semantic_authority": {"none", "candidate", "canonical"},
}
_SAFE_EVIDENCE_KEYS = {"kind", "label", "path", "sha256", "safe_to_share"}
_EXECUTION_KEYS = {
    "runner",
    "entrypoint",
    "working_directory",
    "exit_code",
    "timeout_seconds",
    "timed_out",
    "outcome",
}
_INTEGRITY_KEYS = {
    "manifest_sha256",
    "entrypoint_sha256",
    "manifest_sha256_after",
    "entrypoint_sha256_after",
    "manifest_changed",
    "entrypoint_changed",
}
_REPOSITORY_KEYS = {
    "available",
    "is_repository",
    "repository_root",
    "project_root_matches_repository",
    "branch",
    "commit",
    "dirty_path_count",
}
_RESULT_KEYS = {
    "project_state",
    "safe_summary",
    "warnings",
    "safe_evidence",
    "evidence_count",
    "safe_evidence_count",
    "private_evidence_count",
    "next_action",
    "action_result_present",
    "action_result_valid",
}
_PRIVACY_KEYS = {
    "stdout_stored",
    "stderr_stored",
    "git_diff_stored",
    "file_contents_stored",
}


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be an object.")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append("missing=" + ", ".join(missing))
        if unknown:
            details.append("unknown=" + ", ".join(unknown))
        raise ManifestError(f"{label} fields are invalid ({'; '.join(details)}).")


def _validate_sha(value: Any, label: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ManifestError(f"{label} must be a lowercase SHA-256 digest.")


def _validate_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not _TIMESTAMP_RE.fullmatch(value):
        raise ManifestError(f"{label} must be a UTC RFC 3339 timestamp.")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ManifestError(f"{label} must be a valid UTC timestamp.") from exc


def _validate_repository(value: Any, label: str) -> None:
    obj = _object(value, label)
    _exact_keys(obj, _REPOSITORY_KEYS, label)
    for key in ("available", "is_repository"):
        if not isinstance(obj[key], bool):
            raise ManifestError(f"{label}.{key} must be boolean.")
    if obj["project_root_matches_repository"] is not None and not isinstance(
        obj["project_root_matches_repository"], bool
    ):
        raise ManifestError(
            f"{label}.project_root_matches_repository must be boolean or null."
        )
    for key in ("repository_root", "branch"):
        if obj[key] is not None and not isinstance(obj[key], str):
            raise ManifestError(f"{label}.{key} must be string or null.")
    if obj["commit"] is not None and (
        not isinstance(obj["commit"], str)
        or not _COMMIT_RE.fullmatch(obj["commit"])
    ):
        raise ManifestError(f"{label}.commit must be a Git object id or null.")
    if obj["dirty_path_count"] is not None and (
        not isinstance(obj["dirty_path_count"], int)
        or isinstance(obj["dirty_path_count"], bool)
        or obj["dirty_path_count"] < 0
    ):
        raise ManifestError(f"{label}.dirty_path_count must be nonnegative or null.")


def validate_receipt(
    receipt: Any,
    *,
    manifest: LoadedManifest,
    expected_run_id: str,
) -> dict[str, Any]:
    if not isinstance(expected_run_id, str) or not _RUN_ID_RE.fullmatch(
        expected_run_id
    ):
        raise ManifestError("Expected run id is invalid.")
    value = _object(receipt, "Run receipt")
    _exact_keys(value, _RECEIPT_KEYS, "Run receipt")
    if (
        type(value["contract_version"]) is not int
        or value["contract_version"] != CONTRACT_VERSION
    ):
        raise ManifestError(
            f"Run receipt contract_version must be {CONTRACT_VERSION}."
        )
    if (
        not isinstance(value["runtime_version"], str)
        or not _VERSION_RE.fullmatch(value["runtime_version"])
    ):
        raise ManifestError("Run receipt runtime_version is invalid.")
    if (
        not isinstance(value["run_id"], str)
        or not _RUN_ID_RE.fullmatch(value["run_id"])
        or value["run_id"] != expected_run_id
    ):
        raise ManifestError("Run receipt id does not match the expected run.")

    timestamps = _object(value["timestamps"], "Run receipt timestamps")
    _exact_keys(timestamps, _TIMESTAMP_KEYS, "Run receipt timestamps")
    started_at = _validate_timestamp(timestamps["started_at"], "timestamps.started_at")
    finished_at = _validate_timestamp(
        timestamps["finished_at"], "timestamps.finished_at"
    )
    if finished_at < started_at:
        raise ManifestError("Run receipt finished_at precedes started_at.")

    project = _object(value["project"], "Run receipt project")
    _exact_keys(project, _PROJECT_KEYS, "Run receipt project")
    if project["id"] != manifest.project_id:
        raise ManifestError(
            f"Run receipt project id {project['id']!r} does not match "
            f"{manifest.project_id!r}."
        )
    if (
        not isinstance(project["display_name"], str)
        or not project["display_name"].strip()
        or any(character in project["display_name"] for character in "\r\n\x00")
    ):
        raise ManifestError("Run receipt project display name is invalid.")
    if project["root"] != str(manifest.project_root):
        raise ManifestError("Run receipt project root does not match the manifest.")

    invocation = _object(value["invocation"], "Run receipt invocation")
    _exact_keys(invocation, _INVOCATION_KEYS, "Run receipt invocation")
    if (
        not isinstance(invocation["action"], str)
        or not _ACTION_ID_RE.fullmatch(invocation["action"])
    ):
        raise ManifestError("Run receipt action must be a non-empty string.")
    if invocation["invoked_by"] not in {"human", "local-model-intent"}:
        raise ManifestError("Run receipt invoked_by is invalid.")
    if not isinstance(invocation["parameters"], dict):
        raise ManifestError("Run receipt parameters must be an object.")
    for name, parameter_value in invocation["parameters"].items():
        if not isinstance(name, str) or not _ID_RE.fullmatch(name):
            raise ManifestError("Run receipt parameter name is invalid.")
        if type(parameter_value) not in {bool, str, int}:
            raise ManifestError(
                "Run receipt parameter values must be boolean, string, or integer."
            )

    authority = _object(value["authority"], "Run receipt authority")
    _exact_keys(authority, _AUTHORITY_KEYS, "Run receipt authority")
    for key, allowed in _AUTHORITY_VALUES.items():
        if authority[key] not in allowed:
            raise ManifestError(f"Run receipt authority.{key} is invalid.")

    execution = _object(value["execution"], "Run receipt execution")
    _exact_keys(execution, _EXECUTION_KEYS, "Run receipt execution")
    if execution["runner"] not in ALLOWED_RUNNERS:
        raise ManifestError("Run receipt runner is invalid.")
    if not isinstance(execution["entrypoint"], str) or not isinstance(
        execution["working_directory"], str
    ):
        raise ManifestError("Run receipt execution paths must be strings.")
    resolve_inside(
        manifest.project_root,
        execution["entrypoint"],
        label="Run receipt execution.entrypoint",
    )
    resolve_inside(
        manifest.project_root,
        execution["working_directory"],
        label="Run receipt execution.working_directory",
    )
    if not isinstance(execution["exit_code"], int) or isinstance(
        execution["exit_code"], bool
    ):
        raise ManifestError("Run receipt exit_code must be an integer.")
    if (
        not isinstance(execution["timeout_seconds"], int)
        or isinstance(execution["timeout_seconds"], bool)
        or not 1 <= execution["timeout_seconds"] <= 86400
    ):
        raise ManifestError("Run receipt timeout_seconds must be positive.")
    if not isinstance(execution["timed_out"], bool):
        raise ManifestError("Run receipt timed_out must be boolean.")
    if execution["outcome"] not in ALLOWED_OUTCOMES:
        raise ManifestError("Run receipt outcome is invalid.")

    integrity = _object(value["integrity"], "Run receipt integrity")
    _exact_keys(integrity, _INTEGRITY_KEYS, "Run receipt integrity")
    _validate_sha(integrity["manifest_sha256"], "integrity.manifest_sha256")
    _validate_sha(integrity["entrypoint_sha256"], "integrity.entrypoint_sha256")
    _validate_sha(
        integrity["manifest_sha256_after"],
        "integrity.manifest_sha256_after",
        nullable=True,
    )
    _validate_sha(
        integrity["entrypoint_sha256_after"],
        "integrity.entrypoint_sha256_after",
        nullable=True,
    )
    for key in ("manifest_changed", "entrypoint_changed"):
        if not isinstance(integrity[key], bool):
            raise ManifestError(f"Run receipt integrity.{key} must be boolean.")
    if integrity["manifest_changed"] != (
        integrity["manifest_sha256_after"] != integrity["manifest_sha256"]
    ):
        raise ManifestError("Run receipt manifest change flag is inconsistent.")
    if integrity["entrypoint_changed"] != (
        integrity["entrypoint_sha256_after"] != integrity["entrypoint_sha256"]
    ):
        raise ManifestError("Run receipt entrypoint change flag is inconsistent.")

    _validate_repository(value["repository_before"], "repository_before")
    _validate_repository(value["repository_after"], "repository_after")

    result = _object(value["result"], "Run receipt result")
    _exact_keys(result, _RESULT_KEYS, "Run receipt result")
    if result["project_state"] not in ALLOWED_PROJECT_STATES:
        raise ManifestError("Run receipt project state is invalid.")
    if result["safe_summary"] is not None and not isinstance(
        result["safe_summary"], str
    ):
        raise ManifestError("Run receipt safe_summary must be string or null.")
    if isinstance(result["safe_summary"], str) and len(result["safe_summary"]) > 1000:
        raise ManifestError("Run receipt safe_summary is too long.")
    if not isinstance(result["warnings"], list) or not all(
        isinstance(item, str) and len(item) <= 1000
        for item in result["warnings"]
    ):
        raise ManifestError("Run receipt warnings must be strings up to 1000 characters.")
    if not isinstance(result["safe_evidence"], list):
        raise ManifestError("Run receipt safe_evidence must be an array.")
    for index, item in enumerate(result["safe_evidence"]):
        evidence = _object(item, f"Run receipt safe_evidence[{index}]")
        required = {"kind", "label", "safe_to_share"}
        missing = sorted(required - set(evidence))
        unknown = sorted(set(evidence) - _SAFE_EVIDENCE_KEYS)
        if missing or unknown:
            raise ManifestError(
                f"Run receipt safe_evidence[{index}] fields are invalid."
            )
        if evidence["safe_to_share"] is not True:
            raise ManifestError("Run receipt safe evidence must be marked safe_to_share.")
        if not isinstance(evidence["kind"], str) or not evidence["kind"].strip():
            raise ManifestError("Run receipt safe evidence kind must be non-empty.")
        if not isinstance(evidence["label"], str) or not evidence["label"].strip():
            raise ManifestError("Run receipt safe evidence label must be non-empty.")
        if "path" in evidence:
            if not isinstance(evidence["path"], str):
                raise ManifestError("Run receipt safe evidence path must be a string.")
            resolve_inside(
                manifest.project_root,
                evidence["path"],
                label=f"Run receipt safe_evidence[{index}].path",
            )
        if "sha256" in evidence:
            _validate_sha(
                evidence["sha256"],
                f"Run receipt safe_evidence[{index}].sha256",
            )
    for key in ("evidence_count", "safe_evidence_count", "private_evidence_count"):
        if (
            not isinstance(result[key], int)
            or isinstance(result[key], bool)
            or result[key] < 0
        ):
            raise ManifestError(f"Run receipt result.{key} must be nonnegative.")
    if result["evidence_count"] != (
        result["safe_evidence_count"] + result["private_evidence_count"]
    ):
        raise ManifestError("Run receipt evidence counts are inconsistent.")
    if result["safe_evidence_count"] != len(result["safe_evidence"]):
        raise ManifestError("Run receipt safe evidence count is inconsistent.")
    if result["next_action"] is not None and (
        not isinstance(result["next_action"], str)
        or not result["next_action"].strip()
        or len(result["next_action"]) > 1000
        or "\x00" in result["next_action"]
    ):
        raise ManifestError(
            "Run receipt next_action must be a non-empty string up to 1000 characters "
            "or null."
        )
    for key in ("action_result_present", "action_result_valid"):
        if not isinstance(result[key], bool):
            raise ManifestError(f"Run receipt result.{key} must be boolean.")
    if result["action_result_valid"] and not result["action_result_present"]:
        raise ManifestError("A valid action result must also be present.")

    privacy = _object(value["privacy"], "Run receipt privacy")
    _exact_keys(privacy, _PRIVACY_KEYS, "Run receipt privacy")
    if any(privacy[key] is not False for key in _PRIVACY_KEYS):
        raise ManifestError("Every run receipt privacy assertion must be false.")
    return value


def write_receipt(
    manifest: LoadedManifest, run_id: str, receipt: dict[str, Any]
) -> Path:
    validated = validate_receipt(
        receipt,
        manifest=manifest,
        expected_run_id=run_id,
    )
    run_directory = manifest.state_directory / "runs" / run_id
    receipt_path = run_directory / "receipt.json"
    atomic_write_json(receipt_path, validated)
    pointer = {
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id,
        "receipt_path": relative_posix(receipt_path, manifest.project_root),
        "receipt_sha256": sha256_file(receipt_path),
    }
    atomic_write_json(manifest.state_directory / "latest.json", pointer)
    return receipt_path


def load_latest(manifest: LoadedManifest) -> dict[str, Any]:
    pointer_path = manifest.state_directory / "latest.json"
    pointer = _object(load_json(pointer_path), "Latest receipt pointer")
    _exact_keys(pointer, _POINTER_KEYS, "Latest receipt pointer")
    if (
        type(pointer["contract_version"]) is not int
        or pointer["contract_version"] != CONTRACT_VERSION
    ):
        raise ManifestError(
            f"Latest receipt pointer contract_version must be {CONTRACT_VERSION}."
        )
    run_id = pointer["run_id"]
    if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id):
        raise ManifestError("Latest receipt pointer run_id is invalid.")
    if not isinstance(pointer["receipt_path"], str):
        raise ManifestError("Latest receipt pointer receipt_path must be a string.")
    _validate_sha(pointer["receipt_sha256"], "Latest receipt pointer digest")
    receipt_path = resolve_inside(
        manifest.project_root,
        pointer["receipt_path"],
        label="latest receipt_path",
    )
    expected_path = (
        manifest.state_directory / "runs" / run_id / "receipt.json"
    ).resolve()
    if receipt_path != expected_path:
        raise ManifestError(
            "Latest receipt pointer must reference the matching run receipt path."
        )
    if not receipt_path.is_file():
        raise ManifestError(f"Latest run receipt does not exist: {receipt_path}")
    actual_digest = sha256_file(receipt_path)
    if actual_digest != pointer["receipt_sha256"]:
        raise ManifestError("Latest run receipt digest does not match its pointer.")
    receipt = validate_receipt(
        load_json(receipt_path),
        manifest=manifest,
        expected_run_id=run_id,
    )
    return {**pointer, "receipt": receipt}
