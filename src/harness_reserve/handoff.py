from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import RUNTIME_VERSION
from .git_state import get_git_state
from .manifest import LoadedManifest
from .receipts import load_latest
from .util import atomic_write_json, atomic_write_text, utc_now


def build_handoff(manifest: LoadedManifest) -> tuple[dict[str, Any], Path, Path]:
    latest = load_latest(manifest)
    receipt = latest["receipt"]
    created_at = utc_now()
    safe_evidence = receipt.get("result", {}).get("safe_evidence", [])
    next_action = receipt.get("result", {}).get("next_action")
    outcome = receipt.get("execution", {}).get("outcome", "UNKNOWN")
    action_id = receipt.get("invocation", {}).get("action", "unknown")
    project_state = receipt.get("result", {}).get("project_state", "UNKNOWN")
    receipt_path = latest["receipt_path"]
    receipt_sha256 = latest["receipt_sha256"]
    prompt = (
        f"Continue work in {manifest.display_name} ({manifest.project_id}). "
        f"Read the repository AGENTS.md and .harness-reserve/operator.json first. "
        f"The latest deterministic operator action was {action_id!r}, with outcome "
        f"{outcome} and aggregate project state {project_state}. "
        f"Inspect receipt {receipt_path!r} and current repository state before acting. "
        "Do not infer private content, repeat failed work blindly, broaden authority, "
        "publish, or modify canonical semantic state merely to make status appear current."
    )
    safe_project = {
        "id": manifest.project_id,
        "display_name": manifest.display_name,
    }
    packet = {
        "contract_version": 1,
        "runtime_version": RUNTIME_VERSION,
        "created_at": created_at,
        "project": safe_project,
        "repository": get_git_state(manifest.project_root),
        "latest_run": {
            "run_id": receipt.get("run_id"),
            "receipt_path": receipt_path,
            "receipt_sha256": receipt_sha256,
            "action": action_id,
            "outcome": outcome,
            "project_state": project_state,
            "safe_summary": receipt.get("result", {}).get("safe_summary"),
            "warning_count": len(receipt.get("result", {}).get("warnings", [])),
            "safe_evidence": safe_evidence,
        },
        "authority_boundaries": [
            "This packet grants no authority to commit, push, publish, deploy, or upload source.",
            "Project instructions and current repository state remain authoritative.",
            "Private action stdout, stderr, file contents, and Git diffs are intentionally absent.",
            "Model-dependent interpretation must not be represented as deterministic operator evidence.",
        ],
        "continuation": {
            "recommended_next_action": next_action,
            "prompt": prompt,
        },
    }
    stamp = created_at.replace(":", "").replace("-", "").replace(".", "")
    stamp = stamp.replace("Z", "Z")
    json_path = manifest.handoff_directory / f"handoff-{stamp}.json"
    md_path = manifest.handoff_directory / f"handoff-{stamp}.md"
    atomic_write_json(json_path, packet)
    markdown = _render_markdown(packet)
    atomic_write_text(md_path, markdown)
    return packet, json_path, md_path


def _render_markdown(packet: dict[str, Any]) -> str:
    project = packet["project"] or {}
    repo = packet["repository"] or {}
    latest = packet["latest_run"]
    continuation = packet["continuation"]
    lines = [
        "# Harness Reserve continuation packet",
        "",
        f"- Project: {project.get('display_name')} (`{project.get('id')}`)",
        f"- Created: {packet['created_at']}",
        f"- Branch: {repo.get('branch') or 'unknown'}",
        f"- Commit: {repo.get('commit') or 'unknown'}",
        f"- Dirty paths: {repo.get('dirty_path_count')}",
        f"- Latest action: `{latest.get('action')}`",
        f"- Outcome: **{latest.get('outcome')}**",
        f"- Project state: **{latest.get('project_state')}**",
        "",
        "## Safe summary",
        "",
        *_markdown_quote(
            latest.get("safe_summary")
            or "No project-supplied safe summary was recorded."
        ),
        "",
        "## Authority boundaries",
        "",
    ]
    lines.extend(f"- {item}" for item in packet["authority_boundaries"])
    lines.extend(
        [
            "",
            "## Recommended next action",
            "",
            *_markdown_quote(
                continuation.get("recommended_next_action")
                or "Inspect current state before choosing."
            ),
            "",
            "## Continuation prompt",
            "",
            continuation["prompt"],
            "",
        ]
    )
    return "\n".join(lines)


def _markdown_quote(value: str) -> list[str]:
    lines = value.splitlines() or [""]
    return [f"> {line}" for line in lines]
