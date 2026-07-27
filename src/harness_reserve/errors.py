from __future__ import annotations


class ReserveError(RuntimeError):
    """Base error for expected fail-closed conditions."""

    exit_code = 20


class DiscoveryError(ReserveError):
    """Raised when a project or manifest cannot be located."""


class ManifestError(ReserveError):
    """Raised when a project manifest is invalid."""


class PolicyError(ReserveError):
    """Raised when an action violates deterministic policy."""


class ExecutionError(ReserveError):
    """Raised when an action cannot be launched safely."""


class ActionFailed(ReserveError):
    """Raised only when a caller requests exception behavior for a failed action."""
