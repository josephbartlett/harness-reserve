# Roadmap

## 0.1 foundation implemented

- dependency-free Python runtime and PowerShell 7 launch path;
- strict discovery, manifest, parameter, authority, intent, result, receipt, latest, and handoff
  contracts;
- portable Windows-safe path validation and reserved state containment;
- exact no-shell process invocation, conservative outcome reconciliation, timeout handling, and
  pre/post entrypoint integrity evidence;
- atomic aggregate receipts plus digest-bound latest pointer;
- worktree-aware Git metadata and state/candidate ignore diagnostics;
- fixed tracked-marker project CMD convenience surface and fail-closed root CMD boundary;
- optional proposal-only `gpt-oss:20b` selection through one fixed-loopback Ollama call, with strict
  select-or-refuse adaptation, dry-run intent storage, bounded I/O, and no provider fallback;
- native-Windows launcher, template, installer, schema, example, and failure-mode validation.

See `VALIDATION.md`; technical validation does not mark the version released.

## Open-weight intent status

The fixed provider boundary, catalog minimization, response validation, no-overwrite storage,
privacy exclusions, failure handling, and two-stage execution separation are covered by mocked
tests. CI does not install Ollama or download `gpt-oss:20b`.

Live provider validation remains future evidence. Ollama is absent from the current host, and its
discrete NVIDIA GPU has 4 GB of VRAM versus OpenAI's
[recommended 16 GB or more](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama)
for `gpt-oss:20b`. A suitable-host smoke should measure selection quality, refusal behavior,
latency, memory use, and provider-log/privacy settings without changing the fixed endpoint/model or
adding a remote fallback.

## Next adoption hardening

- Joey review and explicit acceptance of this foundation;
- one thin, separately authorized real-project adapter, followed by a second materially different
  adopter only if the first reveals no shared-contract defect;
- adapter conformance command if real adoption shows value beyond `validate`, `doctor`, and tests;
- migration notes and a contract changelog before a breaking evolution;
- optional minimal-environment execution and bounded output capture if adopter evidence justifies
  contract changes.

## Candidate protocol

The v1 schema already defines provider identity, input/output hash bindings, validation records,
candidate-relative output paths, and promotion state. Still future and project-owned:

- candidate directory initialization;
- live binding and stale-source verification;
- deterministic domain validators;
- human review receipt;
- promotion/rollback templates.

## Deferred until evidence exists

- bounded maintenance packets and isolated worktree execution;
- OS sandbox providers;
- long-running process lifecycle management;
- background watchers;
- remote project registry;
- arbitrary plugin system;
- a universal local coding agent;
- automatic publication, deployment, or paid API fallback.
