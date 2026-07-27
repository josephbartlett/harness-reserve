# Validation status

This document records bounded technical evidence for the Harness Reserve `0.1.0` foundation. A
technical `PASS` is not Joey's semantic acceptance, a package release, deployment authority, or
permission to adopt the runtime into another project.

## Validation host and repository

Local validation on 2026-07-27 used:

```text
OS: Microsoft Windows NT 10.0.26200.8894
PowerShell: 7.6.3
Python: 3.13.3
Git branch: main
Canonical origin: https://github.com/josephbartlett/harness-reserve.git
```

The directory was genuinely uninitialized when received, so Git was initialized locally on
`main`. The canonical origin was added only after Joey identified it. The intended public source is
MIT licensed, copyright 2026 Joey Bartlett. No tag, GitHub Release, PyPI upload, deployment, or
real-project integration is part of this validation.

The original archive carried file-local Windows Mark-of-the-Web metadata. After the repository root
was verified, those marks were removed only within this checkout. No execution-policy bypass or
machine-wide policy change was used.

## Repository conformance

Command:

```powershell
.\scripts\test.ps1
```

Current integrated pre-bind result:

```text
PASS: scaffold validation completed
44 Python files compiled
13 JSON files parsed
7 schemas and runtime fixtures validated
121 source files bound by SHA-256 inventory
Ran 113 tests in 121.670s
OK
```

The validator compiles Python in memory without creating bytecode, parses JSON with duplicate-key,
non-finite-constant, and numeric-overflow rejection, meta-validates all seven Draft 7 schemas,
executes reference contract fixtures, scans executable sources for forbidden shell/batch patterns,
rejects generated fixture output, and rejects tracked ATTUNE, runtime-state, or candidate content.

The Python runtime remains standard-library only. `jsonschema`, build tooling, Twine, and Gitleaks
are validation tools, not runtime dependencies.

## Native Windows operator and adapter evidence

The following flows were exercised through PowerShell 7 and the reference project:

| Flow | Result |
|---|---|
| `list` | exit 0 |
| `validate` | exit 0 |
| `doctor` | exit 0; state/candidate ignore status visible |
| default `run` / `run use` | PASS, exit 0 |
| `run status` | PASS, exit 0 |
| typed `run process` with `open-after:true` | PASS, exit 0 |
| `run verify` | PASS, exit 0 |
| `latest` | exact digest-bound receipt loaded |
| unconfirmed synthetic `serve-private` | expected BLOCK, exit 20 |
| confirmed synthetic `serve-private` | PASS, exit 0 |
| tracked intent without `--execute` | dry run, exit 0, no process |
| tracked intent with `--execute` | PASS, exit 0 |
| `handoff` | JSON and Markdown written |

Native launcher coverage also proved:

- root `reserve.cmd` always blocks;
- generated and example CMD wrappers expose only default/use/status/process/verify;
- non-default CMD selectors must resolve to the exact tracked marker after a size gate;
- same-size external files, external hardlinks, unknown actions, and trailing arguments block;
- Windows still parses a batch command before the wrapper, so CMD remains a trusted-human
  convenience and is not an untrusted-data boundary;
- PowerShell preserves Unicode and caller environment state without profile or argument-mode
  dependence;
- Python actions use `-X utf8 -B` and do not dirty adopters with bytecode.

A generated adapter under a Unicode temporary path returned `DEGRADED` with project state
`UNCONFIGURED` for default/status and `BLOCK` for use/process/verify. Reinitialization refused
overwrite. Broken destination symlinks and escaping directory reparse points also blocked without
writing through them.

## Packaging evidence

A clean temporary source copy built both sdist and `py3-none-any` wheel with setuptools 82.0.1.
Twine accepted both artifacts. The wheel contained:

- MIT `LICENSE` and ATTUNE provenance `NOTICE`;
- the dependency-free runtime;
- all 14 project-adapter resource files;
- no native binary payload.

The wheel was installed into a clean virtual environment. Installed `harness-reserve init` and
`validate` passed, and the generated `harness.ps1` and `harness.cmd status` both found the installed
console application and returned the expected `DEGRADED` exit 10. No package was uploaded.

## Open-weight local-model evidence

The optional proposal adapter is fixed to one unauthenticated request to:

```text
http://127.0.0.1:11434/v1/chat/completions
model: gpt-oss:20b
```

Mocked transport and policy tests cover the exact select/refuse response, fixed endpoint/model,
catalog minimization, hard authority ceiling, request/response bounds, total deadline, tool-call
rejection, sanitized failures, ignored collision-safe storage, post-provider path revalidation,
dry-run-only proposal behavior, and absence of action receipts.

Ollama is not installed on this host. Its discrete NVIDIA GPU has 4 GB of VRAM, below OpenAI's
recommended 16 GB or more for `gpt-oss:20b`. No live inference, latency, quality, memory, or
provider-log/privacy claim is made. Harness Reserve never downloads a model or falls back to a
hosted or paid API.

## ATTUNE evidence

The selected ATTUNE maintenance source is the clean, remotely recoverable provisional host-state
revision:

```text
repository: https://github.com/josephbartlett/attune-orchestration.git
commit: e55d1194a7da7899fcf601cccba2c941fe91876e
tree: 8bfcb1125f69f957136207ec8755b499765a1bd4
interface: codex-host-state/v1
implementation: 0.3.0
```

The pinned ATTUNE source passed:

- 32 focused adoption/CLI/adapter tests;
- 190 reference/conformance tests in place;
- the same 190 tests from ATTUNE's own clean-checkout conformance path;
- constitution lock, evaluator lock, schemas, checkpoint integrity, and topology checks.

ATTUNE reports `project_status: provisional` and `release_authority: false`. Its separate
public-readiness state remains `BLOCK`; Harness Reserve does not claim ATTUNE is released or public.
The Harness integration is a thin optional maintainer binding, not a product dependency or operator
authority source.

The tracked scaffold consists only of the host config, host declaration, thin generated wrapper,
and explicit ignore/line-ending rules. The ATTUNE object repository, materialized closure,
create-only binding, lock, input, and state remain ignored under `.attune/` and outside the
SHA-256 source inventory. Because the binding includes the exact host commit and tree, it is created
only after the immutable initial commit exists; that post-commit verification cannot be embedded in
the commit it verifies.

## Security and privacy review

Focused architecture, security/privacy, Windows/adoption, documentation, and failure-mode reviews
identified and resolved:

- numeric-overflow JSON reaching non-standard `Infinity`;
- portable shebang/script smuggling through `runner: executable`;
- unbounded final pipe drain after an action timeout;
- Python action bytecode dirtying adopting projects;
- broken destination symlinks during adapter initialization;
- same-size external paths selecting a CMD action;
- scaffold checks accidentally excluding the generated state they intended to detect;
- stale private local paths and stale validation counts;
- missing NOTICE propagation and installed-wheel wrapper resolution;
- provider-catalog and human dry-run documentation overclaims.

Receipts and handoffs store no stdout, stderr, file contents, Git diffs, transcript prose, model
reasoning, or sensitive parameter values. Tests bind latest-pointer identity/digests, reject
tampering, and prove a synthetic private marker is absent from persisted receipts and handoffs.
Local paths and project-supplied fields marked safe can still be sensitive and require review before
sharing.

Gitleaks 8.30.1 was downloaded from its GitHub release, verified against the published SHA-256, and
found no secret in the intended source tree. The final committed history is scanned again before
publication.

## Evidence that remains post-commit or out of scope

The immutable initial commit SHA, exact ATTUNE host binding, and hosted Ubuntu/Windows/package
checks cannot be embedded in that same commit without changing it. The ignored binding and GitHub's
checks on the exact commit are therefore the authoritative post-commit evidence and are verified
before repository visibility changes.

The following are intentionally not claimed:

- live Ollama/gpt-oss operation on suitable hardware;
- ATTUNE fresh-clone rehydration or routine rebinding;
- ATTUNE release/public readiness or lifecycle advancement;
- candidate generation, semantic validation, or promotion;
- bounded maintenance worktree execution;
- OS sandboxing, signed receipts, or complete descendant-process containment;
- real harness adoption, package publication, tag/release, deployment, or human acceptance.

The next smallest product action after this foundation is a separate, thin adoption in one real
project, with its own custody, authority, and human-acceptance gates.
