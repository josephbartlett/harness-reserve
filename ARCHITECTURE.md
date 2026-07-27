# Architecture map

Harness Reserve has one shared runtime and many project-owned adapters. The shared runtime owns the
closed operator contract; each adopting repository owns all domain behavior.

## Implemented execution paths

```text
Trusted human convenience
  harness.cmd: default | use | status | process | verify
      |
      v
  harness.ps1
      |
      v
  reserve.ps1 --project-root <project> run <fixed action>
      |
      +---------------------------------------+
                                              |
Human management                              v
  reserve.ps1 list | validate | doctor | describe | run | latest | handoff
      |                                       |
      +--------------------+------------------+
                           v
                  Harness Reserve runtime
  discovery -> strict manifest -> confirmation/policy -> exact no-shell process
                           |                              |
                           |                              v
                           |                    project-owned tracked action
                           |                              |
                           +------------------------------+
                                          |
                                          v
                              aggregate receipt + latest pointer
```

The repository-level `reserve.cmd` is intentionally fail-closed. The general Windows management
entrypoint is `reserve.ps1`. The project `harness.cmd` wrapper is a trusted-human convenience for
four fixed tracked-marker actions and the default action; it does not transport typed or trailing
arguments. A selector must resolve to its exact marker identity, not merely match its size.
`harness.ps1` is the project wrapper for the full declared action surface.

Local-model intent uses two separate stages:

```text
Human request
    |
    v
reserve.ps1 propose-intent --request <text>
    |
    v
fixed 127.0.0.1:11434 Ollama gpt-oss:20b request
    |
    v
strict select-or-refuse data -> deterministic intent validation
    |
    +-> validated intent below ignored state + dry-run plan
             |
             v
reserve.ps1 dispatch-intent <file>
             |
             +-> dry-run by default
             |
             +-> explicit human --execute
                         |
                         v
               same closed operator runtime
```

The deterministic dispatcher remains provider-independent. The optional proposal adapter makes one
fixed-loopback provider call but cannot execute an action. A project launcher does not turn natural
language into a command line, and confirmation cannot raise a model-selected action above the model
authority ceiling. There is no remote endpoint setting, provider credential, retry, or paid
fallback.

## Planes and implementation status

### Operator plane — implemented

The operator plane discovers a project manifest, validates its complete closed shape, resolves
repository-relative paths, binds typed parameters, applies confirmation and Git-state constraints,
invokes an exact entrypoint with `shell=False`, reconciles process and action-result outcomes, and
writes aggregate evidence.

### Intent plane — implemented and optional

The proposal adapter sends only the bounded user request and a reduced catalog of confirmation-free,
low-authority `model_invocable` actions to fixed local Ollama `gpt-oss:20b`. A strict
select-or-refuse response is adapted into the existing six-field intent, revalidated
deterministically, stored without overwrite below `.harness-reserve/state/intents/`, and returned as
a dry run. It creates no action receipt or latest pointer.

The separate dispatcher accepts one fixed intent JSON object, requires the matching project id and
an explicitly `model_invocable` action, reapplies stricter parameter, Git-state, and authority
rules, and produces another dry run unless a human supplies `--execute`.

### Candidate plane — protocol only

`candidate-manifest.schema.json` and the local-model protocol define a conservative shape for
project-owned work below `.harness-reserve/candidates/`. The proposal adapter selects operator
actions only; it does not create candidates, validate their source bindings, or promote them. An
adopter that implements those operations must keep generation and promotion separate and must prove
canonical files were not overwritten.

### Maintenance plane — future

Bounded repair in a disposable worktree is deliberately unimplemented. It requires a
project-specific isolation and diff-review design; it must not be represented as an open shell
inside the operator contract.

## Ownership boundary

The shared runtime owns:

- project and manifest discovery;
- strict contract validation and portable path containment;
- typed parameter binding and deterministic confirmation;
- exact Python, PowerShell 7, or native-executable invocation;
- timeout handling and conservative result reconciliation;
- receipts, latest pointers, safe continuation handoffs, intent validation, adapter generation, and
  the optional fixed-loopback proposal adapter.

The adopting repository owns:

```text
.harness-reserve/operator.json
.harness-reserve/actions/
.harness-reserve/cmd-actions/
harness.cmd
harness.ps1
```

Those adapters delegate to existing project launchers, pipelines, tests, custody rules, and
orchestration. The shared repository must not learn how a domain transcribes input, starts an app,
interprets evidence, deploys, or publishes.

## State and integrity boundary

Runtime state must resolve at or below:

```text
.harness-reserve/state/
```

The handoff directory must resolve at or below the selected state directory. Candidate storage is a
separate ignored tree at `.harness-reserve/candidates/`. Adopters must ignore both; `doctor` reports
an explicitly unignored tree as not ready, but Harness Reserve is not a confidentiality boundary.

Each executed action receives a unique run directory:

```text
.harness-reserve/state/
  latest.json
  runs/<run-id>/
    action-result.json
    receipt.json
  intents/
    <timestamp>-<random>.intent.json
  handoffs/
    handoff-<timestamp>.json
    handoff-<timestamp>.md
```

Proposal intents always use the reserved `.harness-reserve/state/intents/` location, even when a
manifest selects a deeper runtime state directory. The proposer blocks unless Git verifies that
reserved directory as ignored, rejects symlink/reparse ancestors, and revalidates the destination
after the provider wait before publishing the file. A proposal intent is inspectable input to the
dispatcher, not a receipt and not delegated execution authority.

`latest.json` is an exact pointer containing the run id, receipt-relative path, and receipt SHA-256.
Loading it validates the pointer path, digest, receipt shape, and project/run identity. The receipt
records manifest and entrypoint hashes before and after execution; observed mutation forces
`ERROR` and suppresses project-supplied result details.

These checks detect consistency failures, not hostile forgery. State is unsigned and an actor able
to rewrite both a receipt and its pointer can replace them. Receipts and handoffs are local,
privacy-minimized operational artifacts rather than public attestations.

## Authority boundary

Capability declarations drive review and deterministic confirmation, but they do not restrict the
operating system. Project scripts and their environment remain in the trusted computing base.

Likewise, a bounded technical result is not a human or lifecycle decision:

```text
action PASS
    does not imply
human acceptance -> semantic approval -> release authorization -> publication/deployment
```

See `docs/DESIGN.md` for rationale, `docs/CONTRACT.md` for exact fields, and
`docs/SECURITY_MODEL.md` for limits.
