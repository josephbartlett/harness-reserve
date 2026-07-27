# Execution plan 0001: Harness Reserve foundation

Status: completed; technical foundation accepted for the governed publication pass
Owner: repository maintainer

## Goal

Establish the shared closed operator contract, dependency-free reference runtime, fail-closed
project adapter, synthetic example, schemas, tests, and executable documentation required before a
separately authorized real-project adoption.

## Completed implementation

- [x] Define separate operator, intent, candidate-protocol, and future-maintenance planes.
- [x] Keep all domain behavior in project-owned adapters.
- [x] Implement strict JSON, manifest, action-result, intent, receipt, latest, and handoff validation.
- [x] Require explicit six-dimensional authority, typed parameters, redaction, and hard confirmation.
- [x] Enforce portable Windows-safe paths, reserved state containment, and no-shell invocation.
- [x] Support exact Python, PowerShell 7, and native-executable runners.
- [x] Reconcile exit/result outcomes conservatively and handle start failure and timeout.
- [x] Write atomic receipts and a digest/path/run-bound latest pointer.
- [x] Bind pre/post manifest and entrypoint hashes and fail on observed drift.
- [x] Sanitize Git inspection and diagnose state/candidate ignore readiness.
- [x] Validate low-authority model intent with default dry run and portable-token parameters.
- [x] Generate a no-overwrite, reparse-safe, human-only adapter that blocks by default.
- [x] Provide fixed tracked-marker project CMD convenience plus an authoritative PowerShell argument path.
- [x] Define and schema-test candidate-only bindings without claiming a generic generator/promoter.
- [x] Dogfood all reference actions, receipts, latest, handoff, confirmation, and intent flows.
- [x] Validate the runtime, launchers, installer, template, and example on native Windows.
- [x] Align all seven schemas, code, tests, examples, decisions, and operator documentation.

## Evidence

Host:

```text
Windows NT 10.0.26200.0
PowerShell 7.6.3
Python 3.13.3
```

Repository conformance validates every Python source without writing bytecode, strictly parses every
tracked JSON document, meta-validates seven Draft 7 schemas, applies a dependency-free UTC
date-time checker, and validates runtime-emitted manifest/result/receipt/latest/handoff plus intent
and candidate fixtures.

Native acceptance includes:

- `scripts/test.ps1`;
- list, validate, doctor, status, default/use, typed process, verify, latest, and handoff;
- expected unconfirmed private-LAN BLOCK 20 and confirmed synthetic PASS;
- eligible status intent dry-run and execution;
- project `harness.cmd` default/status/process/verify plus extra-input BLOCK;
- repository `reserve.cmd` fail-closed BLOCK;
- Unicode/space-path adapter initialization;
- generated PowerShell and CMD status returning exit 10 with `DEGRADED`/`UNCONFIGURED`;
- initialization overwrite refusal;
- receipt/handoff privacy inspection and generated-state cleanup.

Exact final command counts and outcomes are recorded in `VALIDATION.md`.

Focused reviews:

- contract/schema reviewer: closed-shape parity, candidate rules, receipt/run identity, date/time,
  version typing, and runtime fixture validation;
- security/privacy reviewer: path/reparse/ADS, confirmation, Git, model ceiling, receipt leakage,
  pointer tamper, and integrity drift;
- Windows/adoption reviewer: PowerShell argument fidelity, Unicode, execution-policy posture, CMD
  selector boundary, installer, template outcomes, and missing-runtime behavior;
- acceptance/failure-mode reviewer: criterion-to-test coverage, exact native executable, ignore
  guidance, caller-package shadow resistance, and remaining professional-cliff risks.

## Decisions

- The runtime remains Python 3.11+ standard library; `jsonschema` is validation-only.
- PowerShell 7 is the general Windows transport. Root `reserve.cmd` blocks, while project
  `harness.cmd` exposes only fixed tracked-marker, argument-free actions.
- State stays below `.harness-reserve/state`; latest is a digest-bound pointer.
- Model intent is optional, low-authority, token-only, and dry-run by default.
- Candidate work is a schema/protocol; generation, review, and promotion are project-owned.
- Maintenance worktrees remain future and cannot introduce an operator-plane shell.
- ATTUNE remains separate and authoritative for its own lifecycle.
- No license is selected.

## Remaining risks and deliberate limits

- This is not an OS sandbox; authority metadata cannot restrain a dishonest trusted action.
- Child environment and command-line arguments may expose secrets to the host.
- Action stdout/stderr capture is unbounded in memory and exists transiently.
- Process-tree timeout cleanup is best effort, not Windows Job Object containment.
- Existing-path checks and post-run hashes do not eliminate concurrent reparse/replacement races.
- Git, Python, PowerShell, and native tools remain part of the trusted host toolchain.
- Receipt digests are consistency bindings, not signatures; a writer controlling all state can forge
  a new consistent pair.
- Project-asserted safe summaries/evidence are not content-classified or independently re-hashed.
- CMD is a fixed human convenience, not an untrusted-data boundary.
- Candidate generation/promotion and bounded maintenance are protocol/future capability only.

## Explicitly outside this run

- real-project integration or copying private project content;
- generic model-provider integration;
- generic candidate promotion or maintenance execution;
- commit, tag, remote configuration, push, publication, deployment, or license selection;
- Joey acceptance or release authorization inferred from technical PASS.

## Next smallest useful action

Joey reviews the uncommitted greenfield foundation and either accepts it or records exact changes.
After explicit acceptance and separate authority, initialize one thin adopter and map only its
aggregate `status` action to an existing project-owned entrypoint.
