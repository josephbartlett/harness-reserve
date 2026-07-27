# Decision 0005: confine runtime state and bind the latest receipt

Status: accepted for the reference foundation

## Context

A merely project-relative state path can target canonical project files. An unbound `latest.json`
can point at an unrelated or modified receipt. A single pre-run entrypoint hash does not reveal
whether the manifest or selected entrypoint changed or disappeared during execution.

Receipts must stay aggregate and useful for continuation without becoming signatures, private logs,
or grants of authority.

## Decision

- Runtime state must resolve at or below `.harness-reserve/state`.
- Handoffs must resolve at or below the selected state directory.
- Each run writes an exact receipt below `state/runs/<run-id>/`.
- `latest.json` is an exact pointer containing contract version, run id, the expected relative
  receipt path, and its SHA-256.
- Loading latest validates pointer shape, expected path, digest, receipt shape, run id, project id,
  and project root.
- Receipts record manifest and entrypoint hashes before and after execution. Observed change or
  disappearance forces `ERROR` and suppresses project-supplied summary, state, evidence, and next
  action.
- Handoffs are built only from a validated latest receipt, bind its path and digest, and explicitly
  grant no commit, push, publication, deployment, or semantic authority.
- Generic receipts and handoffs omit stdout, stderr, file contents, and Git diffs.

## Consequences

State cannot be redirected onto arbitrary canonical project paths through the manifest. Stale,
misdirected, or accidentally modified latest receipts fail closed, and observed action-definition
drift cannot be reported as a successful trusted result.

Each JSON file uses atomic replacement, but a crash may leave an orphan run before the latest pointer
advances. The hashes provide consistency and observed-drift detection, not authenticity: state is
unsigned, and an actor able to rewrite the receipt and pointer can forge a new consistent pair.

Receipts and handoffs remain local operational artifacts. Their technical validity does not imply
human review, semantic approval, lifecycle promotion, or release authorization.
