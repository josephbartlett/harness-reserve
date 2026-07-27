from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import uuid
from typing import Any

from .action_result import (
    conservative_outcome,
    load_action_result,
    outcome_from_exit_code,
)
from .constants import RUNTIME_VERSION
from .errors import ExecutionError, ManifestError, PolicyError
from .git_state import get_git_state
from .manifest import (
    LoadedManifest,
    validate_native_executable,
    validate_parameter_values,
)
from .policy import (
    assert_confirmed,
    assert_model_invocable,
    build_arguments,
    build_redacted_arguments,
    redact_parameters,
)
from .receipts import write_receipt
from .util import relative_posix, resolve_inside, sha256_file, utc_now


@dataclass
class ExecutionResult:
    receipt: dict[str, Any]
    receipt_path: Path | None
    stdout: str
    stderr: str
    command_preview: list[str]


@dataclass
class _ProcessCapture:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    launch_error: str | None
    termination_warning: str | None


def _timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def _find_powershell() -> str:
    for name in ("pwsh.exe", "pwsh"):
        value = shutil.which(name)
        if value:
            return value
    raise ExecutionError("BLOCK: PowerShell 7 (pwsh) is required for this action.")


def _terminate_process_tree(process: subprocess.Popen[str]) -> str | None:
    if os.name == "nt":
        taskkill = shutil.which("taskkill.exe") or shutil.which("taskkill")
        if taskkill:
            try:
                completed = subprocess.run(
                    [taskkill, "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                    shell=False,
                )
                if completed.returncode == 0:
                    return None
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            process.kill()
        except OSError:
            return "Timed-out process tree termination was incomplete."
        return (
            "Timed-out process was killed directly, but descendant termination "
            "could not be confirmed."
        )

    try:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=2)
            return None
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            return None
    except OSError:
        try:
            process.kill()
        except OSError:
            pass
        return "Timed-out process tree termination was incomplete."


def _run_process(
    command: list[str],
    *,
    working_directory: Path,
    environment: dict[str, str],
    timeout_seconds: int,
) -> _ProcessCapture:
    popen_options: dict[str, Any] = {}
    if os.name == "nt":
        popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_options["start_new_session"] = True
    try:
        process = subprocess.Popen(
            command,
            cwd=working_directory,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            **popen_options,
        )
    except (OSError, ValueError):
        return _ProcessCapture(
            exit_code=1,
            stdout="",
            stderr="",
            timed_out=False,
            launch_error="Action process could not start.",
            termination_warning=None,
        )

    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return _ProcessCapture(
            exit_code=process.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            timed_out=False,
            launch_error=None,
            termination_warning=None,
        )
    except subprocess.TimeoutExpired:
        termination_warning = _terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired as final_timeout:
            try:
                process.kill()
            except OSError:
                pass
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            try:
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
            stdout = _timeout_output(final_timeout.output)
            stderr = _timeout_output(final_timeout.stderr)
            termination_warning = (
                termination_warning
                or "Timed-out process output pipes did not close after bounded termination."
            )
        return _ProcessCapture(
            exit_code=124,
            stdout=stdout or "",
            stderr=stderr or "",
            timed_out=True,
            launch_error=f"Action exceeded its {timeout_seconds} second timeout.",
            termination_warning=termination_warning,
        )


def _sha256_after(path: Path) -> str | None:
    try:
        return sha256_file(path)
    except OSError:
        return None



def build_command(
    manifest: LoadedManifest, action: dict[str, Any], arguments: list[str]
) -> tuple[list[str], Path, Path]:
    entrypoint = resolve_inside(
        manifest.project_root,
        action["entrypoint"],
        label="action.entrypoint",
    )
    working_directory = resolve_inside(
        manifest.project_root,
        action.get("working_directory", "."),
        label="action.working_directory",
    )
    if not entrypoint.is_file():
        raise ExecutionError(f"BLOCK: Action entry point is missing: {entrypoint}")
    if not working_directory.is_dir():
        raise ExecutionError(
            f"BLOCK: Action working directory is missing: {working_directory}"
        )
    runner = action["runner"]
    if runner == "python":
        command = [
            sys.executable,
            "-X",
            "utf8",
            "-B",
            str(entrypoint),
            *arguments,
        ]
    elif runner == "powershell":
        command = [
            _find_powershell(),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(entrypoint),
            *arguments,
        ]
    elif runner == "executable":
        validate_native_executable(entrypoint, label="action.entrypoint")
        command = [str(entrypoint), *arguments]
    else:  # Manifest validation should make this unreachable.
        raise ExecutionError(f"BLOCK: Unsupported runner: {runner!r}.")
    return command, entrypoint, working_directory


def _git_clean_required(
    manifest: LoadedManifest, action_id: str, git_state: dict[str, Any]
) -> None:
    required = manifest.raw["constraints"].get("require_clean_git_for", [])
    if action_id not in required:
        return
    dirty = git_state.get("dirty_path_count")
    if dirty is None:
        raise PolicyError(
            f"BLOCK: Action {action_id!r} requires a clean Git worktree, but Git state is unavailable."
        )
    if dirty > 0:
        raise PolicyError(
            f"BLOCK: Action {action_id!r} requires a clean Git worktree; {dirty} dirty paths were found."
        )


def execute_action(
    manifest: LoadedManifest,
    action_id: str | None,
    supplied_parameters: dict[str, Any],
    *,
    confirmed: bool = False,
    confirmation_text: str | None = None,
    invoked_by: str = "human",
    dry_run: bool = False,
) -> ExecutionResult:
    selected = action_id or manifest.default_action
    action = manifest.action(selected)
    resolved_parameters = validate_parameter_values(selected, action, supplied_parameters)
    if invoked_by not in {"human", "local-model-intent"}:
        raise PolicyError(f"BLOCK: Unknown invocation origin: {invoked_by!r}.")

    assert_confirmed(
        action,
        confirmed=confirmed,
        confirmation_text=confirmation_text,
    )
    arguments = build_arguments(action, resolved_parameters)
    command, entrypoint, working_directory = build_command(manifest, action, arguments)
    redacted_parameters = redact_parameters(action, resolved_parameters)
    redacted_arguments = build_redacted_arguments(action, resolved_parameters)
    redacted_command, _, _ = build_command(
        manifest, action, redacted_arguments
    )
    git_before = get_git_state(manifest.project_root)
    _git_clean_required(manifest, selected, git_before)

    if invoked_by == "local-model-intent":
        assert_model_invocable(
            selected,
            action,
            git_dirty=bool(git_before.get("dirty_path_count")),
            forbid_when_dirty=manifest.raw["constraints"].get(
                "forbid_model_actions_when_dirty", True
            ),
            resolved_parameters=resolved_parameters,
        )

    if dry_run:
        plan = {
            "contract_version": 1,
            "runtime_version": RUNTIME_VERSION,
            "dry_run": True,
            "project_id": manifest.project_id,
            "action": selected,
            "runner": action["runner"],
            "entrypoint": relative_posix(entrypoint, manifest.project_root),
            "working_directory": relative_posix(
                working_directory, manifest.project_root
            ),
            "arguments": redacted_arguments,
            "parameters": redacted_parameters,
            "authority": action["authority"],
            "invoked_by": invoked_by,
        }
        return ExecutionResult(
            receipt=plan,
            receipt_path=None,
            stdout="",
            stderr="",
            command_preview=redacted_command,
        )

    try:
        manifest_sha256_before = sha256_file(manifest.manifest_path)
        entrypoint_sha256_before = sha256_file(entrypoint)
    except OSError as exc:
        raise ExecutionError(
            f"BLOCK: Action integrity could not be captured before launch: {exc}"
        ) from exc

    run_id = _run_id()
    run_directory = manifest.state_directory / "runs" / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    action_result_path = run_directory / "action-result.json"

    environment = os.environ.copy()
    environment.update(action.get("environment", {}))
    environment.update(
        {
            "HARNESS_RESERVE_RUNTIME_VERSION": RUNTIME_VERSION,
            "HARNESS_RESERVE_PROJECT_ROOT": str(manifest.project_root),
            "HARNESS_RESERVE_PROJECT_ID": manifest.project_id,
            "HARNESS_RESERVE_ACTION": selected,
            "HARNESS_RESERVE_RUN_ID": run_id,
            "HARNESS_RESERVE_RUN_DIR": str(run_directory),
            "HARNESS_RESERVE_RESULT_PATH": str(action_result_path),
            "HARNESS_RESERVE_INVOKED_BY": invoked_by,
        }
    )

    started_at = utc_now()
    capture = _run_process(
        command,
        working_directory=working_directory,
        environment=environment,
        timeout_seconds=action["timeout_seconds"],
    )
    finished_at = utc_now()
    process_outcome = outcome_from_exit_code(
        capture.exit_code, timed_out=capture.timed_out
    )
    manifest_sha256_after = _sha256_after(manifest.manifest_path)
    entrypoint_sha256_after = _sha256_after(entrypoint)
    manifest_changed = manifest_sha256_after != manifest_sha256_before
    entrypoint_changed = entrypoint_sha256_after != entrypoint_sha256_before

    action_result: dict[str, Any] | None = None
    result_error: str | None = None
    action_result_present = action_result_path.is_file()
    try:
        action_result = load_action_result(
            action_result_path,
            project_root=manifest.project_root,
        )
    except ManifestError as exc:
        result_error = str(exc)
    action_result_valid = action_result is not None

    outcome = process_outcome
    if action_result is not None:
        outcome = conservative_outcome(outcome, action_result["outcome"])
    if (
        result_error
        or capture.launch_error
        or manifest_changed
        or entrypoint_changed
    ):
        outcome = "ERROR"

    safe_evidence = []
    warnings: list[str] = []
    project_state = "UNKNOWN"
    safe_summary = None
    next_action = None
    evidence_count = 0
    safe_evidence_count = 0
    private_evidence_count = 0
    process_overrode_result = bool(
        action_result
        and process_outcome != action_result["outcome"]
        and conservative_outcome(process_outcome, action_result["outcome"])
        == process_outcome
    )
    result_usable = bool(
        action_result
        and not process_overrode_result
        and not result_error
        and not capture.launch_error
        and not manifest_changed
        and not entrypoint_changed
    )
    if result_usable and action_result is not None:
        all_evidence = action_result.get("evidence", [])
        safe_evidence = [
            item for item in all_evidence if item["safe_to_share"]
        ]
        warnings.extend(action_result.get("warnings", []))
        project_state = action_result.get("project_state", "UNKNOWN")
        safe_summary = action_result.get("safe_summary")
        next_action = action_result.get("next_action")
        evidence_count = len(all_evidence)
        safe_evidence_count = len(safe_evidence)
        private_evidence_count = evidence_count - safe_evidence_count
    if process_overrode_result and action_result is not None:
        warnings.append(
            "Action result was less conservative than the process exit and its "
            "summary, state, evidence, and next step were suppressed."
        )
    if result_error:
        warnings.append(
            "Action result was rejected by the closed contract; inspect the "
            "project-local action result for details."
        )
    if capture.launch_error:
        warnings.append(capture.launch_error)
    if capture.termination_warning:
        warnings.append(capture.termination_warning)
    if manifest_changed:
        warnings.append(
            "The operator manifest changed or disappeared during execution; "
            "the action result was suppressed."
        )
    if entrypoint_changed:
        warnings.append(
            "The action entrypoint changed or disappeared during execution; "
            "the action result was suppressed."
        )

    git_after = get_git_state(manifest.project_root)
    receipt = {
        "contract_version": 1,
        "runtime_version": RUNTIME_VERSION,
        "run_id": run_id,
        "timestamps": {"started_at": started_at, "finished_at": finished_at},
        "project": {
            "id": manifest.project_id,
            "display_name": manifest.display_name,
            "root": str(manifest.project_root),
        },
        "invocation": {
            "action": selected,
            "invoked_by": invoked_by,
            "parameters": redacted_parameters,
        },
        "authority": action["authority"],
        "execution": {
            "runner": action["runner"],
            "entrypoint": relative_posix(entrypoint, manifest.project_root),
            "working_directory": relative_posix(
                working_directory, manifest.project_root
            ),
            "exit_code": capture.exit_code,
            "timeout_seconds": action["timeout_seconds"],
            "timed_out": capture.timed_out,
            "outcome": outcome,
        },
        "integrity": {
            "manifest_sha256": manifest_sha256_before,
            "entrypoint_sha256": entrypoint_sha256_before,
            "manifest_sha256_after": manifest_sha256_after,
            "entrypoint_sha256_after": entrypoint_sha256_after,
            "manifest_changed": manifest_changed,
            "entrypoint_changed": entrypoint_changed,
        },
        "repository_before": git_before,
        "repository_after": git_after,
        "result": {
            "project_state": project_state,
            "safe_summary": safe_summary,
            "warnings": warnings,
            "safe_evidence": safe_evidence,
            "evidence_count": evidence_count,
            "safe_evidence_count": safe_evidence_count,
            "private_evidence_count": private_evidence_count,
            "next_action": next_action,
            "action_result_present": action_result_present,
            "action_result_valid": action_result_valid,
        },
        "privacy": {
            "stdout_stored": False,
            "stderr_stored": False,
            "git_diff_stored": False,
            "file_contents_stored": False,
        },
    }
    receipt_path = write_receipt(manifest, run_id, receipt)
    return ExecutionResult(
        receipt=receipt,
        receipt_path=receipt_path,
        stdout=capture.stdout,
        stderr=capture.stderr,
        command_preview=redacted_command,
    )
