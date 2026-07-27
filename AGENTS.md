# AGENTS.md

Harness Reserve is a small, domain-agnostic operator contract and reference runtime. Keep this file
as a map, not an encyclopedia.

## Read order

1. `README.md`
2. `ARCHITECTURE.md`
3. `docs/DESIGN.md`
4. `docs/CONTRACT.md`
5. `docs/SECURITY_MODEL.md`
6. `docs/ADOPTION.md`
7. `docs/ADAPTER_PATTERNS.md`
8. `docs/LOCAL_MODEL_PROTOCOL.md` when model integration is in scope
9. `docs/MAINTAINING.md` for repository governance or release work
10. the active plan in `docs/exec-plans/active/`

## Core invariants

- Project repositories own domain behavior; this repository owns only the shared operator contract.
- Never add arbitrary shell passthrough, `shell=True`, `Invoke-Expression`, or model-provided paths.
- Entrypoints and working directories must resolve inside the adopting project root.
- Unknown actions, parameters, manifest fields, and intent fields fail closed.
- Direct human invocation and model intent invocation are separate paths.
- A model may select only actions explicitly marked `model_invocable`.
- Sensitive authority always requires deterministic confirmation regardless of manifest preference.
- Receipts do not store command output, secrets, transcript prose, file contents, or Git diffs.
- Local semantic work is candidate-only until deterministic validation and explicit human promotion.
- ATTUNE evidence never grants merge, publication, release, or lifecycle authority.
- This runtime is not an OS sandbox. Do not claim stronger isolation than it provides.
- Keep the Python runtime standard-library only unless a demonstrated need justifies a dependency.
- Preserve Windows-first usability while keeping the core portable.

## Work discipline

- Prefer focused, test-backed changes.
- Update contracts, schemas, docs, examples, and tests together when behavior changes.
- Run `python -m unittest discover -s tests -v` with `PYTHONPATH=src`.
- Do not publish, push, select a license, or integrate a real project without explicit instruction.
- Report limitations honestly, especially when PowerShell or Windows behavior was not exercised.
