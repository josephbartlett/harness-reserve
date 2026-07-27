# Project adapter

This directory belongs to the adopting project. It declares the small set of ordinary local actions
that remain useful without a hosted coding agent.

The generated actions are intentionally fail-closed. Replace each stub with a thin adapter around an
existing tracked project script. Do not reimplement the app launcher, ingestion pipeline, test suite,
or custody rules here.

Project-owned files:

- `operator.json` - action and authority declaration.
- `actions/` - thin, tracked entry points.
- `cmd-actions/` - fixed markers used by the exact-identity CMD convenience surface.
- `gitignore.append` - lines that should be merged into the root `.gitignore`.

Shared runtime state is written under `.harness-reserve/state/` and should remain ignored.
Candidate-only model output should use `.harness-reserve/candidates/` and remain ignored.

`harness.ps1` resolves the shared runtime from `HARNESS_RESERVE_HOME`, a project submodule, a sibling
checkout, or a trusted installed `harness-reserve` application on `PATH`, in that order.

The default/status action returns `DEGRADED` plus `UNCONFIGURED`; use/process/verify block. Every
generated action is `model_invocable: false`. Audit and replace a stub before changing either
behavior.

`harness.cmd` accepts only the default and four exact tracked-marker actions
use/status/process/verify, with no trailing arguments. Use `harness.ps1` for typed parameters or
additional declared actions. The adapter should delegate to existing project scripts rather than
duplicate pipelines.
