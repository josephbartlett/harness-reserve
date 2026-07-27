from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys
from typing import Any

from .constants import (
    ALLOWED_RUNNERS,
    CONTRACT_VERSION,
    DEFAULT_HANDOFF_DIRECTORY,
    DEFAULT_STATE_DIRECTORY,
    RUNTIME_VERSION,
)
from .errors import ManifestError
from .util import (
    load_json,
    parse_version,
    resolve_inside,
    safe_env_name,
    safe_id,
)

_TOP_LEVEL_KEYS = {
    "$schema",
    "contract_version",
    "runtime",
    "project",
    "default_action",
    "state",
    "actions",
    "constraints",
    "extensions",
}
_RUNTIME_KEYS = {"minimum_version"}
_PROJECT_KEYS = {"id", "display_name", "description", "platforms"}
_STATE_KEYS = {"directory", "handoff_directory"}
_CONSTRAINT_KEYS = {
    "require_clean_git_for",
    "forbid_model_actions_when_dirty",
    "extensions",
}
_ACTION_KEYS = {
    "description",
    "runner",
    "entrypoint",
    "working_directory",
    "fixed_args",
    "parameters",
    "environment",
    "timeout_seconds",
    "authority",
    "confirmation",
    "model_invocable",
    "extensions",
}
_PARAMETER_KEYS = {
    "type",
    "flag",
    "required",
    "default",
    "sensitive",
    "values",
    "minimum",
    "maximum",
    "pattern",
    "description",
}
_AUTHORITY_KEYS = {
    "filesystem",
    "network",
    "git",
    "external_systems",
    "secrets",
    "semantic_authority",
}
_CONFIRMATION_KEYS = {"mode", "prompt", "phrase"}

_AUTHORITY_VALUES = {
    "filesystem": {"read-only", "derived-only", "workspace-write", "unrestricted-project"},
    "network": {"none", "loopback", "private-lan", "internet"},
    "git": {"none", "read", "write", "publish"},
    "external_systems": {"none", "read", "write"},
    "secrets": {"none", "read"},
    "semantic_authority": {"none", "candidate", "canonical"},
}
_CONFIRMATION_MODES = {"none", "explicit", "phrase"}
_PARAMETER_TYPES = {"boolean", "string", "integer", "enum"}
_PLATFORM_VALUES = {"windows", "linux", "macos"}
_ACTION_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_MAX_PARAMETER_STRING_LENGTH = 4096
_WINDOWS_NATIVE_EXECUTABLE_SUFFIXES = {".exe", ".com"}
_FORBIDDEN_EXECUTABLE_SCRIPT_SUFFIXES = {
    ".bat",
    ".cmd",
    ".hta",
    ".js",
    ".jse",
    ".lnk",
    ".msc",
    ".ps1",
    ".psm1",
    ".py",
    ".pyw",
    ".rb",
    ".sh",
    ".tcl",
    ".url",
    ".vbe",
    ".vbs",
    ".wsf",
    ".wsh",
}
_ELF_MAGIC = b"\x7fELF"
_MACH_O_MAGICS = {
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
}


@dataclass(frozen=True)
class LoadedManifest:
    project_root: Path
    manifest_path: Path
    raw: dict[str, Any]

    @property
    def project(self) -> dict[str, Any]:
        return self.raw["project"]

    @property
    def project_id(self) -> str:
        return str(self.project["id"])

    @property
    def display_name(self) -> str:
        return str(self.project["display_name"])

    @property
    def actions(self) -> dict[str, dict[str, Any]]:
        return self.raw["actions"]

    @property
    def default_action(self) -> str:
        return str(self.raw["default_action"])

    @property
    def state_directory(self) -> Path:
        value = self.raw.get("state", {}).get("directory", DEFAULT_STATE_DIRECTORY)
        return resolve_inside(self.project_root, value, label="state.directory")

    @property
    def handoff_directory(self) -> Path:
        value = self.raw.get("state", {}).get(
            "handoff_directory", DEFAULT_HANDOFF_DIRECTORY
        )
        return resolve_inside(self.project_root, value, label="state.handoff_directory")

    def action(self, action_id: str) -> dict[str, Any]:
        try:
            return self.actions[action_id]
        except KeyError as exc:
            options = ", ".join(sorted(self.actions))
            raise ManifestError(
                f"Unknown action {action_id!r}. Declared actions: {options}."
            ) from exc


def _assert_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be a JSON object.")
    return value


def _assert_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ManifestError(f"{label} has unknown fields: {', '.join(unknown)}.")


def _optional_object(value: Any, label: str) -> dict[str, Any]:
    return _assert_object(value, label)


def _validate_extensions(value: Any, label: str) -> dict[str, Any]:
    return _assert_object(value, label)


def _validate_runtime(runtime: Any) -> dict[str, Any]:
    runtime_obj = _optional_object(runtime, "runtime")
    _assert_keys(runtime_obj, _RUNTIME_KEYS, "runtime")
    minimum = runtime_obj.get("minimum_version", "0.1.0")
    if not isinstance(minimum, str):
        raise ManifestError("runtime.minimum_version must be a version string.")
    if parse_version(RUNTIME_VERSION) < parse_version(minimum):
        raise ManifestError(
            f"Manifest requires Harness Reserve {minimum} or later; runtime is {RUNTIME_VERSION}."
        )
    runtime_obj["minimum_version"] = minimum
    return runtime_obj


def _validate_project(project: Any) -> dict[str, Any]:
    project_obj = _assert_object(project, "project")
    _assert_keys(project_obj, _PROJECT_KEYS, "project")
    for required in ("id", "display_name"):
        if required not in project_obj:
            raise ManifestError(f"project.{required} is required.")
    if not isinstance(project_obj["id"], str):
        raise ManifestError("project.id must be a string.")
    safe_id(project_obj["id"], label="project.id")
    if not isinstance(project_obj["display_name"], str) or not project_obj[
        "display_name"
    ].strip():
        raise ManifestError("project.display_name must be a non-empty string.")
    if any(character in project_obj["display_name"] for character in "\r\n\x00"):
        raise ManifestError("project.display_name must be one line and contain no nulls.")
    description = project_obj.get("description")
    if "description" in project_obj and not isinstance(description, str):
        raise ManifestError("project.description must be a string.")
    platforms = project_obj.get("platforms", ["windows"])
    if not isinstance(platforms, list) or not platforms:
        raise ManifestError("project.platforms must be a non-empty array.")
    if not all(isinstance(item, str) for item in platforms):
        raise ManifestError("project.platforms entries must be strings.")
    invalid = [item for item in platforms if item not in _PLATFORM_VALUES]
    if invalid:
        raise ManifestError(f"Unsupported project platforms: {invalid!r}.")
    if len(set(platforms)) != len(platforms):
        raise ManifestError("project.platforms must not contain duplicates.")
    project_obj["platforms"] = platforms
    return project_obj


def _validate_state(state: Any, root: Path) -> dict[str, Any]:
    state_obj = _optional_object(state, "state")
    _assert_keys(state_obj, _STATE_KEYS, "state")
    state_obj.setdefault("directory", DEFAULT_STATE_DIRECTORY)
    state_obj.setdefault("handoff_directory", DEFAULT_HANDOFF_DIRECTORY)
    reserve_state_root = resolve_inside(
        root, DEFAULT_STATE_DIRECTORY, label="reserved state root"
    )
    state_path = resolve_inside(root, state_obj["directory"], label="state.directory")
    if state_path != reserve_state_root and reserve_state_root not in state_path.parents:
        raise ManifestError(
            "state.directory must resolve at or below '.harness-reserve/state'."
        )
    handoff_path = resolve_inside(
        root, state_obj["handoff_directory"], label="state.handoff_directory"
    )
    if handoff_path != state_path and state_path not in handoff_path.parents:
        raise ManifestError(
            "state.handoff_directory must resolve at or below state.directory."
        )
    return state_obj


def _validate_confirmation(value: Any, label: str) -> dict[str, Any]:
    obj = _optional_object(value, label)
    _assert_keys(obj, _CONFIRMATION_KEYS, label)
    mode = obj.get("mode", "none")
    if not isinstance(mode, str) or mode not in _CONFIRMATION_MODES:
        raise ManifestError(f"{label}.mode must be one of {sorted(_CONFIRMATION_MODES)}.")
    prompt = obj.get("prompt", "Confirm this action.")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ManifestError(f"{label}.prompt must be a non-empty string.")
    phrase = obj.get("phrase")
    if mode == "phrase" and (
        not isinstance(phrase, str) or not phrase.strip() or "\x00" in phrase
    ):
        raise ManifestError(f"{label}.phrase is required when mode is 'phrase'.")
    if mode != "phrase" and "phrase" in obj:
        raise ManifestError(f"{label}.phrase is only valid when mode is 'phrase'.")
    return {"mode": mode, "prompt": prompt, **({"phrase": phrase} if phrase else {})}


def _validate_authority(value: Any, label: str) -> dict[str, str]:
    obj = _assert_object(value, label)
    _assert_keys(obj, _AUTHORITY_KEYS, label)
    missing = sorted(_AUTHORITY_KEYS - set(obj))
    if missing:
        raise ManifestError(
            f"{label} must declare every authority field; missing: {', '.join(missing)}."
        )
    for key, allowed in _AUTHORITY_VALUES.items():
        if not isinstance(obj[key], str) or obj[key] not in allowed:
            raise ManifestError(
                f"{label}.{key} must be one of {sorted(allowed)}; received {obj[key]!r}."
            )
    return dict(obj)


def _validate_parameter(name: str, value: Any, label: str) -> dict[str, Any]:
    safe_id(name, label=f"{label} parameter name")
    obj = _assert_object(value, f"{label}.{name}")
    _assert_keys(obj, _PARAMETER_KEYS, f"{label}.{name}")
    kind = obj.get("type")
    if not isinstance(kind, str) or kind not in _PARAMETER_TYPES:
        raise ManifestError(
            f"{label}.{name}.type must be one of {sorted(_PARAMETER_TYPES)}."
        )
    flag = obj.get("flag")
    if (
        not isinstance(flag, str)
        or not flag.strip()
        or "\x00" in flag
        or any(ch.isspace() for ch in flag)
    ):
        raise ManifestError(f"{label}.{name}.flag must be one non-empty token.")
    required = obj.get("required", False)
    sensitive = obj.get("sensitive", False)
    if not isinstance(required, bool) or not isinstance(sensitive, bool):
        raise ManifestError(f"{label}.{name} required/sensitive values must be boolean.")
    if kind == "enum":
        values = obj.get("values")
        if not isinstance(values, list) or not values or not all(
            isinstance(item, str) and "\x00" not in item for item in values
        ):
            raise ManifestError(f"{label}.{name}.values must be a non-empty string array.")
        if len(set(values)) != len(values):
            raise ManifestError(f"{label}.{name}.values must not contain duplicates.")
    elif "values" in obj:
        raise ManifestError(f"{label}.{name}.values is only valid for enum parameters.")
    if kind == "integer":
        for key in ("minimum", "maximum"):
            if key in obj and (
                not isinstance(obj[key], int) or isinstance(obj[key], bool)
            ):
                raise ManifestError(f"{label}.{name}.{key} must be an integer.")
        if (
            "minimum" in obj
            and "maximum" in obj
            and obj["minimum"] > obj["maximum"]
        ):
            raise ManifestError(f"{label}.{name} minimum exceeds maximum.")
    elif "minimum" in obj or "maximum" in obj:
        raise ManifestError(
            f"{label}.{name} minimum/maximum are only valid for integer parameters."
        )
    if "pattern" in obj:
        if kind != "string":
            raise ManifestError(f"{label}.{name}.pattern is only valid for string parameters.")
        try:
            re.compile(obj["pattern"])
        except (TypeError, re.error) as exc:
            raise ManifestError(f"{label}.{name}.pattern is invalid: {exc}") from exc
    description = obj.get("description")
    if "description" in obj and not isinstance(description, str):
        raise ManifestError(f"{label}.{name}.description must be a string.")
    if "default" in obj:
        _validate_parameter_value(name, obj["default"], obj, label)
    return obj


def _validate_parameter_value(
    name: str, value: Any, spec: dict[str, Any], label: str
) -> Any:
    kind = spec["type"]
    if kind == "boolean":
        if not isinstance(value, bool):
            raise ManifestError(f"{label}.{name} must be boolean.")
    elif kind == "string":
        if not isinstance(value, str) or "\x00" in value:
            raise ManifestError(f"{label}.{name} must be a string.")
        if len(value) > _MAX_PARAMETER_STRING_LENGTH:
            raise ManifestError(
                f"{label}.{name} exceeds the {_MAX_PARAMETER_STRING_LENGTH}-character limit."
            )
        pattern = spec.get("pattern")
        if pattern and not re.fullmatch(pattern, value):
            raise ManifestError(f"{label}.{name} does not match its required pattern.")
    elif kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ManifestError(f"{label}.{name} must be an integer.")
        if "minimum" in spec and value < spec["minimum"]:
            raise ManifestError(f"{label}.{name} is below its minimum.")
        if "maximum" in spec and value > spec["maximum"]:
            raise ManifestError(f"{label}.{name} exceeds its maximum.")
    elif kind == "enum":
        if (
            not isinstance(value, str)
            or "\x00" in value
            or value not in spec["values"]
        ):
            raise ManifestError(
                f"{label}.{name} must be one of {spec['values']!r}."
            )
    return value


def validate_native_executable(path: Path, *, label: str) -> None:
    suffix = path.suffix.lower()
    if suffix in _FORBIDDEN_EXECUTABLE_SCRIPT_SUFFIXES:
        raise ManifestError(
            f"{label} uses script/document suffix {suffix!r}; "
            "the executable runner accepts native executables only."
        )
    if os.name == "nt":
        if suffix not in _WINDOWS_NATIVE_EXECUTABLE_SUFFIXES:
            raise ManifestError(
                f"{label} must end in .exe or .com on Windows when "
                "runner is 'executable'."
            )
        return
    try:
        with path.open("rb") as handle:
            magic = handle.read(4)
    except OSError as exc:
        raise ManifestError(
            f"{label} could not be inspected as a native executable."
        ) from exc
    if sys.platform == "darwin":
        valid_magic = magic in _MACH_O_MAGICS
        expected = "Mach-O"
    else:
        valid_magic = magic == _ELF_MAGIC
        expected = "ELF"
    if not valid_magic:
        raise ManifestError(
            f"{label} is not a recognized {expected} native executable; "
            "scripts and unrecognized formats require an explicit runner."
        )


def _validate_action(
    action_id: str, value: Any, root: Path, *, check_files: bool
) -> dict[str, Any]:
    if not _ACTION_ID_RE.fullmatch(action_id):
        raise ManifestError(
            f"Action id {action_id!r} must match {_ACTION_ID_RE.pattern!r}."
        )
    label = f"actions.{action_id}"
    obj = _assert_object(value, label)
    _assert_keys(obj, _ACTION_KEYS, label)
    for required in ("description", "runner", "entrypoint"):
        if required not in obj:
            raise ManifestError(f"{label}.{required} is required.")
    if not isinstance(obj["description"], str) or not obj["description"].strip():
        raise ManifestError(f"{label}.description must be a non-empty string.")
    runner = obj["runner"]
    if not isinstance(runner, str) or runner not in ALLOWED_RUNNERS:
        raise ManifestError(f"{label}.runner must be one of {sorted(ALLOWED_RUNNERS)}.")
    entrypoint = resolve_inside(root, obj["entrypoint"], label=f"{label}.entrypoint")
    suffix = entrypoint.suffix.lower()
    if runner == "executable":
        if suffix in _FORBIDDEN_EXECUTABLE_SCRIPT_SUFFIXES:
            raise ManifestError(
                f"{label}.entrypoint uses script/document suffix {suffix!r}; "
                "the executable runner accepts native executables only."
            )
        if os.name == "nt" and suffix not in _WINDOWS_NATIVE_EXECUTABLE_SUFFIXES:
            raise ManifestError(
                f"{label}.entrypoint must end in .exe or .com on Windows when "
                "runner is 'executable'."
            )
    if check_files and not entrypoint.is_file():
        raise ManifestError(f"{label}.entrypoint does not exist: {entrypoint}")
    if runner == "executable" and check_files:
        validate_native_executable(entrypoint, label=f"{label}.entrypoint")
    working = obj.get("working_directory", ".")
    working_path = resolve_inside(root, working, label=f"{label}.working_directory")
    if check_files and not working_path.is_dir():
        raise ManifestError(f"{label}.working_directory does not exist: {working_path}")
    fixed_args = obj.get("fixed_args", [])
    if not isinstance(fixed_args, list) or not all(
        isinstance(item, str) and "\x00" not in item for item in fixed_args
    ):
        raise ManifestError(f"{label}.fixed_args must be an array of strings.")
    parameters = _assert_object(obj.get("parameters", {}), f"{label}.parameters")
    validated_parameters = {
        name: _validate_parameter(name, spec, f"{label}.parameters")
        for name, spec in parameters.items()
    }
    flags = [spec["flag"] for spec in validated_parameters.values()]
    if len(flags) != len(set(flags)):
        raise ManifestError(f"{label}.parameters must use unique flag tokens.")
    environment = _assert_object(obj.get("environment", {}), f"{label}.environment")
    for key, val in environment.items():
        safe_env_name(key)
        if not isinstance(val, str) or "\x00" in val:
            raise ManifestError(f"{label}.environment.{key} must be a string.")
    timeout = obj.get("timeout_seconds", 3600)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 86400:
        raise ManifestError(f"{label}.timeout_seconds must be between 1 and 86400.")
    model_invocable = obj.get("model_invocable", False)
    if not isinstance(model_invocable, bool):
        raise ManifestError(f"{label}.model_invocable must be boolean.")
    if "authority" not in obj:
        raise ManifestError(f"{label}.authority is required.")
    authority = _validate_authority(obj["authority"], f"{label}.authority")
    confirmation = _validate_confirmation(
        obj.get("confirmation", {}), f"{label}.confirmation"
    )
    if "extensions" in obj:
        _validate_extensions(obj["extensions"], f"{label}.extensions")
    return {
        **obj,
        "working_directory": working,
        "fixed_args": fixed_args,
        "parameters": validated_parameters,
        "environment": environment,
        "timeout_seconds": timeout,
        "model_invocable": model_invocable,
        "authority": authority,
        "confirmation": confirmation,
    }


def _validate_constraints(value: Any, action_ids: set[str]) -> dict[str, Any]:
    obj = _optional_object(value, "constraints")
    _assert_keys(obj, _CONSTRAINT_KEYS, "constraints")
    clean_for = obj.get("require_clean_git_for", [])
    if not isinstance(clean_for, list) or not all(isinstance(item, str) for item in clean_for):
        raise ManifestError("constraints.require_clean_git_for must be a string array.")
    if len(set(clean_for)) != len(clean_for):
        raise ManifestError(
            "constraints.require_clean_git_for must not contain duplicates."
        )
    unknown = sorted(set(clean_for) - action_ids)
    if unknown:
        raise ManifestError(
            f"constraints.require_clean_git_for names unknown actions: {', '.join(unknown)}."
        )
    forbid_model_dirty = obj.get("forbid_model_actions_when_dirty", True)
    if not isinstance(forbid_model_dirty, bool):
        raise ManifestError("constraints.forbid_model_actions_when_dirty must be boolean.")
    obj["require_clean_git_for"] = clean_for
    obj["forbid_model_actions_when_dirty"] = forbid_model_dirty
    if "extensions" in obj:
        _validate_extensions(obj["extensions"], "constraints.extensions")
    return obj


def load_manifest(
    project_root: Path, manifest_path: Path, *, check_files: bool = True
) -> LoadedManifest:
    root = project_root.resolve()
    resolved_manifest_path = manifest_path.resolve()
    try:
        resolved_manifest_path.relative_to(root)
    except ValueError as exc:
        raise ManifestError(
            f"Manifest must resolve inside the project root: {resolved_manifest_path}."
        ) from exc
    raw_value = load_json(resolved_manifest_path)
    raw = _assert_object(raw_value, "manifest")
    _assert_keys(raw, _TOP_LEVEL_KEYS, "manifest")
    if "$schema" in raw and (
        not isinstance(raw["$schema"], str) or not raw["$schema"]
    ):
        raise ManifestError("manifest.$schema must be a non-empty string.")
    if "extensions" in raw:
        _validate_extensions(raw["extensions"], "manifest.extensions")
    if (
        type(raw.get("contract_version")) is not int
        or raw["contract_version"] != CONTRACT_VERSION
    ):
        raise ManifestError(
            f"contract_version must be {CONTRACT_VERSION}; received {raw.get('contract_version')!r}."
        )
    runtime = _validate_runtime(raw.get("runtime", {}))
    project = _validate_project(raw.get("project"))
    state = _validate_state(raw.get("state", {}), root)
    actions_obj = _assert_object(raw.get("actions"), "actions")
    if not actions_obj:
        raise ManifestError("actions must declare at least one action.")
    actions = {
        action_id: _validate_action(action_id, value, root, check_files=check_files)
        for action_id, value in actions_obj.items()
    }
    default_action = raw.get("default_action")
    if not isinstance(default_action, str) or default_action not in actions:
        raise ManifestError("default_action must name one declared action.")
    constraints = _validate_constraints(raw.get("constraints", {}), set(actions))
    normalized = {
        **raw,
        "contract_version": CONTRACT_VERSION,
        "runtime": runtime,
        "project": project,
        "state": state,
        "default_action": default_action,
        "actions": actions,
        "constraints": constraints,
    }
    return LoadedManifest(
        project_root=root,
        manifest_path=resolved_manifest_path,
        raw=normalized,
    )


def validate_parameter_values(
    action_id: str, action: dict[str, Any], supplied: dict[str, Any]
) -> dict[str, Any]:
    specs = action.get("parameters", {})
    unknown = sorted(set(supplied) - set(specs))
    if unknown:
        raise ManifestError(
            f"Action {action_id!r} received unknown parameters: {', '.join(unknown)}."
        )
    resolved: dict[str, Any] = {}
    for name, spec in specs.items():
        if name in supplied:
            resolved[name] = _validate_parameter_value(
                name, supplied[name], spec, f"action {action_id!r} parameter"
            )
        elif "default" in spec:
            resolved[name] = spec["default"]
        elif spec.get("required", False):
            raise ManifestError(
                f"Action {action_id!r} requires parameter {name!r}."
            )
    return resolved
