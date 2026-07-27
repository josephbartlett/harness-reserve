from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def write_result(
    *,
    outcome: str,
    summary: str,
    project_state: str,
    warnings: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    next_action: str | None = None,
) -> None:
    path_value = os.environ.get("HARNESS_RESERVE_RESULT_PATH")
    if not path_value:
        raise RuntimeError("HARNESS_RESERVE_RESULT_PATH was not supplied")
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract_version": 1,
        "outcome": outcome,
        "safe_summary": summary,
        "project_state": project_state,
        "warnings": warnings or [],
        "evidence": evidence or [],
        "next_action": next_action,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def project_root() -> Path:
    value = os.environ.get("HARNESS_RESERVE_PROJECT_ROOT")
    if not value:
        raise RuntimeError("HARNESS_RESERVE_PROJECT_ROOT was not supplied")
    return Path(value)
