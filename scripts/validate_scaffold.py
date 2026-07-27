from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
EXCLUDED_SCAN_PARTS = {
    ".git",
    ".attune",
    ".venv",
    "__pycache__",
    "state",
    "candidates",
}
LOCAL_TREE_PARTS = {
    ".git",
    ".attune",
    ".venv",
    "build",
    "dist",
}

from harness_reserve.handoff import build_handoff
from harness_reserve.init_project import initialize_adapter
from harness_reserve.intent import dispatch_intent
from harness_reserve.manifest import load_manifest
from harness_reserve.runner import execute_action
from harness_reserve.util import load_json, sha256_file


def fail(message: str) -> None:
    print(f"BLOCK: {message}", file=sys.stderr)
    raise SystemExit(20)


def excluded_from_repository_scan(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return any(part in EXCLUDED_SCAN_PARTS for part in relative.parts)


def excluded_from_cleanliness_check(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return any(
        part in LOCAL_TREE_PARTS or part.endswith(".egg-info")
        for part in relative.parts
    )


def _strict_json(path: Path) -> Any:
    try:
        return load_json(path)
    except Exception as exc:
        fail(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}")


def parse_json_files() -> list[Path]:
    parsed: list[Path] = []
    for path in ROOT.rglob("*.json"):
        if excluded_from_repository_scan(path):
            continue
        _strict_json(path)
        parsed.append(path)
    return parsed


def validate_versions() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    constants = (SRC / "harness_reserve" / "constants.py").read_text(
        encoding="utf-8"
    )
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if f'RUNTIME_VERSION = "{version}"' not in constants:
        fail("VERSION and constants.py disagree")
    if f'version = "{version}"' not in pyproject:
        fail("VERSION and pyproject.toml disagree")


def validate_python_sources() -> int:
    count = 0
    for path in ROOT.rglob("*.py"):
        if excluded_from_repository_scan(path):
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            compile(tree, str(path), "exec", dont_inherit=True)
        except (OSError, SyntaxError, UnicodeError) as exc:
            fail(f"Python source did not compile: {path.relative_to(ROOT)}: {exc}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if any(
                keyword.arg == "shell"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            ):
                fail(f"shell=True is forbidden: {path.relative_to(ROOT)}")
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr == "system"
            ):
                fail(f"os.system is forbidden: {path.relative_to(ROOT)}")
        count += 1
    return count


def validate_script_boundaries() -> None:
    for path in ROOT.rglob("*.ps1"):
        if excluded_from_repository_scan(path):
            continue
        text = path.read_text(encoding="utf-8")
        for marker in ("Invoke-Expression", "-ExecutionPolicy Bypass"):
            if marker.casefold() in text.casefold():
                fail(f"Forbidden PowerShell marker {marker!r}: {path.relative_to(ROOT)}")

    for path in ROOT.rglob("*.cmd"):
        if excluded_from_repository_scan(path):
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"%\*", text):
            fail(f"Batch argument passthrough is forbidden: {path.relative_to(ROOT)}")
        if re.search(r"%(?:~)?[12](?![0-9A-Za-z])", text):
            fail(f"Raw batch argument expansion is forbidden: {path.relative_to(ROOT)}")
        if "EnableDelayedExpansion".casefold() in text.casefold():
            fail(f"Delayed batch expansion is forbidden: {path.relative_to(ROOT)}")


def validate_template() -> None:
    template = (
        SRC
        / "harness_reserve"
        / "resources"
        / "project-adapter"
    )
    required = [
        template / ".harness-reserve" / "operator.json",
        template / "harness.cmd",
        template / "harness.ps1",
        template / ".harness-reserve" / "gitignore.append",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        fail("Missing template files: " + ", ".join(missing))
    manifest_text = required[0].read_text(encoding="utf-8")
    for token in ("__PROJECT_ID__", "__DISPLAY_NAME__"):
        if token not in manifest_text:
            fail(f"Template token is missing: {token}")


def validate_clean_fixture() -> None:
    generated = [
        ROOT / "examples" / "minimal-python-project" / ".harness-reserve" / "state",
        ROOT / "examples" / "minimal-python-project" / ".harness-reserve" / "candidates",
    ]
    generated.extend(ROOT.rglob("__pycache__"))
    generated.extend(ROOT.rglob("*.pyc"))
    existing = [
        str(path.relative_to(ROOT))
        for path in generated
        if path.exists() and not excluded_from_cleanliness_check(path)
    ]
    if existing:
        fail("Generated runtime or Python cache output is present: " + ", ".join(existing))


def validate_tracked_state_boundaries() -> None:
    git_metadata = ROOT / ".git"
    git = shutil.which("git")
    if not git_metadata.exists() or not git:
        return
    try:
        completed = subprocess.run(
            [git, "-C", str(ROOT), "ls-files", "-z"],
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"Tracked-state boundary could not inspect Git: {exc}")
    if completed.returncode != 0:
        fail("Tracked-state boundary could not enumerate the Git index.")
    tracked = [
        Path(os.fsdecode(value))
        for value in completed.stdout.split(b"\x00")
        if value
    ]
    forbidden: list[str] = []
    for path in tracked:
        parts = path.parts
        if parts and parts[0] == ".attune":
            forbidden.append(path.as_posix())
            continue
        for index, part in enumerate(parts[:-1]):
            if (
                part == ".harness-reserve"
                and parts[index + 1] in {"state", "candidates"}
            ):
                forbidden.append(path.as_posix())
                break
    if forbidden:
        fail(
            "Ignored ATTUNE, runtime state, or candidate content is tracked: "
            + ", ".join(sorted(forbidden))
        )


def _validator(schema_root: Path, name: str):
    try:
        import jsonschema
    except ImportError:
        fail(
            "jsonschema is required for repository validation. "
            "Install the validation extra; the runtime itself remains dependency-free."
        )
    schema = load_json(schema_root / name)
    jsonschema.Draft7Validator.check_schema(schema)
    format_checker = jsonschema.FormatChecker()

    @format_checker.checks("date-time")
    def valid_utc_date_time(value: object) -> bool:
        if not isinstance(value, str):
            return True
        if not value.endswith("Z"):
            return False
        try:
            datetime.fromisoformat(value[:-1] + "+00:00")
        except ValueError:
            return False
        return True

    return jsonschema.Draft7Validator(
        schema,
        format_checker=format_checker,
    )


def _assert_schema(validator: Any, instance: Any, label: str) -> None:
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "<root>"
        fail(f"{label} violates its schema at {location}: {error.message}")


def _assert_schema_rejects(validator: Any, instance: Any, label: str) -> None:
    if not list(validator.iter_errors(instance)):
        fail(f"{label} was incorrectly accepted by its schema.")


def _copy_example(destination: Path) -> None:
    source = ROOT / "examples" / "minimal-python-project"
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "state", "candidates"),
    )


def validate_contract_fixtures() -> None:
    schema_root = ROOT / "schemas"
    validators = {
        path.name: _validator(schema_root, path.name)
        for path in sorted(schema_root.glob("*.schema.json"))
    }
    expected = {
        "action-result.schema.json",
        "candidate-manifest.schema.json",
        "handoff-packet.schema.json",
        "latest-pointer.schema.json",
        "operator-intent.schema.json",
        "operator-manifest.schema.json",
        "run-receipt.schema.json",
    }
    if set(validators) != expected:
        fail(
            "Schema inventory differs from the seven contract schemas: "
            f"found={sorted(validators)}"
        )

    example_root = ROOT / "examples" / "minimal-python-project"
    example_manifest = load_json(
        example_root / ".harness-reserve" / "operator.json"
    )
    _assert_schema(
        validators["operator-manifest.schema.json"],
        example_manifest,
        "Reference manifest",
    )
    intent = load_json(example_root / "status.intent.json")
    _assert_schema(
        validators["operator-intent.schema.json"],
        intent,
        "Reference model intent",
    )

    template_text = (
        SRC
        / "harness_reserve"
        / "resources"
        / "project-adapter"
        / ".harness-reserve"
        / "operator.json"
    ).read_text(encoding="utf-8")
    template_manifest = json.loads(
        template_text.replace("__PROJECT_ID__", "schema-project").replace(
            "__DISPLAY_NAME__", "Schema Project"
        )
    )
    _assert_schema(
        validators["operator-manifest.schema.json"],
        template_manifest,
        "Substituted adapter template manifest",
    )

    digest = "0" * 64
    candidate = {
        "contract_version": 1,
        "project_id": "minimal-python-project",
        "candidate_id": "candidate-001",
        "kind": "semantic-note",
        "created_at": "2026-07-26T12:00:00Z",
        "provider": {"name": "local-provider", "model": "local-model"},
        "input_bindings": [{"path": "app.py", "sha256": digest}],
        "outputs": [{"path": "outputs/candidate.txt", "sha256": digest}],
        "validation": {"state": "PENDING", "checks": []},
        "promotion_state": "CANDIDATE",
    }
    _assert_schema(
        validators["candidate-manifest.schema.json"],
        candidate,
        "Synthetic candidate protocol fixture",
    )
    promoted_without_validation = {
        **candidate,
        "promotion_state": "PROMOTED",
    }
    _assert_schema_rejects(
        validators["candidate-manifest.schema.json"],
        promoted_without_validation,
        "Unvalidated promoted candidate",
    )
    canonical_output = {
        **candidate,
        "outputs": [{"path": "docs/canonical.txt", "sha256": digest}],
    }
    _assert_schema_rejects(
        validators["candidate-manifest.schema.json"],
        canonical_output,
        "Candidate output outside candidate output storage",
    )
    invalid_timestamp = {
        **candidate,
        "created_at": "2026-99-99T12:00:00Z",
    }
    _assert_schema_rejects(
        validators["candidate-manifest.schema.json"],
        invalid_timestamp,
        "Candidate with invalid calendar timestamp",
    )

    with tempfile.TemporaryDirectory(prefix="harness-reserve-validation-") as temp:
        temp_root = Path(temp)
        project_root = temp_root / "reference-project"
        _copy_example(project_root)
        manifest = load_manifest(
            project_root,
            project_root / ".harness-reserve" / "operator.json",
        )
        result = execute_action(manifest, "status", {})
        if result.receipt["execution"]["outcome"] != "PASS" or not result.receipt_path:
            fail("Reference status action did not produce a PASS receipt.")

        action_result = load_json(result.receipt_path.parent / "action-result.json")
        _assert_schema(
            validators["action-result.schema.json"],
            action_result,
            "Runtime-emitted action result",
        )
        _assert_schema(
            validators["run-receipt.schema.json"],
            result.receipt,
            "Runtime-emitted run receipt",
        )
        pointer = load_json(manifest.state_directory / "latest.json")
        _assert_schema(
            validators["latest-pointer.schema.json"],
            pointer,
            "Runtime-emitted latest pointer",
        )
        if sha256_file(result.receipt_path) != pointer["receipt_sha256"]:
            fail("Runtime-emitted latest pointer digest does not bind its receipt.")

        packet, json_path, _ = build_handoff(manifest)
        _assert_schema(
            validators["handoff-packet.schema.json"],
            packet,
            "Runtime-emitted handoff packet",
        )
        _assert_schema(
            validators["handoff-packet.schema.json"],
            load_json(json_path),
            "Persisted handoff packet",
        )

        dry_run = dispatch_intent(
            project_root / "status.intent.json",
            manifest,
            execute=False,
            confirmed=False,
            confirmation_text=None,
        )
        if not dry_run.receipt.get("dry_run"):
            fail("Reference local-model intent was not dry-run by default.")
        executed = dispatch_intent(
            project_root / "status.intent.json",
            manifest,
            execute=True,
            confirmed=False,
            confirmation_text=None,
        )
        if executed.receipt["execution"]["outcome"] != "PASS":
            fail("Eligible reference local-model intent did not execute successfully.")

        initialized = temp_root / "initialized-project"
        initialized.mkdir()
        initialize_adapter(
            initialized,
            project_id="initialized-project",
            display_name="Initialized Project",
        )
        initialized_manifest = load_json(
            initialized / ".harness-reserve" / "operator.json"
        )
        _assert_schema(
            validators["operator-manifest.schema.json"],
            initialized_manifest,
            "Initialized adapter manifest",
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_scaffold_manifest() -> None:
    manifest_path = ROOT / "SCAFFOLD_MANIFEST.json"
    if not manifest_path.is_file():
        fail("SCAFFOLD_MANIFEST.json is missing")
    value = load_json(manifest_path)
    records = value.get("files")
    if not isinstance(records, list):
        fail("SCAFFOLD_MANIFEST.json files must be an array")
    recorded = {item.get("path"): item for item in records if isinstance(item, dict)}
    current: dict[str, Path] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name in {manifest_path.name, ".DS_Store"}:
            continue
        relative = path.relative_to(ROOT)
        if excluded_from_repository_scan(path) or path.suffix == ".pyc":
            continue
        current[relative.as_posix()] = path
    if set(recorded) != set(current):
        missing = sorted(set(current) - set(recorded))
        stale = sorted(set(recorded) - set(current))
        fail(
            "Scaffold manifest file set differs; regenerate it. "
            f"Missing={missing}, stale={stale}"
        )
    for relative, path in current.items():
        item = recorded[relative]
        if (
            item.get("size_bytes") != path.stat().st_size
            or item.get("sha256") != _sha256(path)
        ):
            fail(f"Scaffold manifest hash differs for {relative}; regenerate it")
    if value.get("file_count") != len(current):
        fail("Scaffold manifest file_count is incorrect")


def main() -> int:
    validate_versions()
    parsed = parse_json_files()
    python_count = validate_python_sources()
    validate_script_boundaries()
    validate_template()
    validate_clean_fixture()
    validate_tracked_state_boundaries()
    validate_contract_fixtures()
    validate_scaffold_manifest()
    print(
        "PASS: scaffold validation completed "
        f"({python_count} Python files compiled, {len(parsed)} JSON files parsed, "
        "7 schemas and runtime fixtures validated)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
