# Decision 0004: keep Windows batch launchers fixed and fail-closed

Status: accepted for the reference foundation

## Context

Windows parses a `.cmd` invocation before the batch file can validate its arguments. Raw `%*`,
`%1`, or reconstructed caller text can therefore turn a convenience wrapper into command injection
or lossy argument transport. PowerShell native argument behavior can also vary with caller settings.

The project still needs the familiar literal commands `harness.cmd`, `harness.cmd status`,
`harness.cmd process`, and `harness.cmd verify`.

## Decision

- Repository-level `reserve.cmd` always returns `BLOCK`; general management uses `reserve.ps1`.
- Project `harness.cmd` recognizes only the default and fixed `use`, `status`, `process`, and
  `verify` actions through exact tracked marker identity after a metadata-only size gate.
- Project batch wrappers reject every extra argument and never place caller text into an executed
  command.
- Typed parameters and all other actions use `harness.ps1` or `reserve.ps1`.
- `reserve.ps1` serializes its received argument array as JSON on standard input to a small Python
  bridge, independent of PowerShell native argument-passing modes. It starts Python in isolated
  UTF-8 mode and inserts only the selected checkout's `src` path so caller projects cannot shadow
  the shared package and Unicode arguments retain their identity.
- Launchers respect execution policy and do not use `-ExecutionPolicy Bypass`.
- No model, filename, network value, or other untrusted text may be routed through `.cmd`.

## Consequences

The required human convenience commands remain available, while batch is not represented as a
general closed dispatcher. Equivalent paths to an exact tracked marker may select the same fixed
action, but same-size external files do not. Adding a project action to the manifest does not
automatically add it to `harness.cmd`; extending that fixed surface requires an explicit audited
launcher change.

The initial Windows command processor remains outside the runtime's security boundary. Untrusted
data must enter through typed JSON handled by PowerShell and the Python runtime.

This decision is an implementation and security boundary. It is not evidence of human acceptance or
release authorization.
