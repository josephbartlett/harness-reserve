from __future__ import annotations

RUNTIME_VERSION = "0.1.0"
CONTRACT_VERSION = 1
MANIFEST_RELATIVE_PATH = ".harness-reserve/operator.json"
DEFAULT_STATE_DIRECTORY = ".harness-reserve/state"
DEFAULT_HANDOFF_DIRECTORY = ".harness-reserve/state/handoffs"

ALLOWED_RUNNERS = {"python", "powershell", "executable"}
ALLOWED_OUTCOMES = {"PASS", "DEGRADED", "BLOCK", "ERROR"}
ALLOWED_PROJECT_STATES = {
    "READY",
    "DEGRADED",
    "BLOCKED",
    "STALE",
    "UNCONFIGURED",
    "UNKNOWN",
}

EXIT_PASS = 0
EXIT_DEGRADED = 10
EXIT_BLOCK = 20
EXIT_ERROR = 1

SENSITIVE_AUTHORITY = {
    ("network", "private-lan"),
    ("network", "internet"),
    ("git", "write"),
    ("git", "publish"),
    ("external_systems", "write"),
    ("secrets", "read"),
    ("semantic_authority", "canonical"),
    ("filesystem", "unrestricted-project"),
}
