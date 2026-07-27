# Harness Reserve

Harness Reserve is a small, domain-agnostic local operator contract and reference runtime. It keeps
known project workflows usable when hosted Codex is unavailable or unnecessary, without trying to
recreate a coding agent.

The repository separates three concerns:

1. **Operator plane — implemented.** Deterministic discovery, validation, policy, exact invocation,
   aggregate receipts, and continuation handoffs.
2. **Intent plane — implemented and optional.** The fixed-loopback proposal adapter may ask local
   Ollama `gpt-oss:20b` to select one eligible action. Harness Reserve converts that selection into
   its existing intent contract, validates it, stores it locally, and produces a dry run. Execution
   remains a separate explicit dispatch.
3. **Candidate plane — protocol only.** A schema and conservative rules describe project-owned,
   ignored candidate work. The core does not generate, validate, or promote candidates.

Bounded maintenance in an isolated worktree is future design work. It is not an operator action and
must never become arbitrary shell authority.

Each adopting project remains authoritative for its launchers, pipelines, tests, custody, privacy,
semantic interpretation, deployment, and publication. This repository owns only the shared
operator contract and reference implementation.

## Project-facing commands

The generated Windows adapter preserves a small convenience surface:

```powershell
.\harness.cmd
.\harness.cmd status
.\harness.cmd process
.\harness.cmd verify
```

`harness.cmd` is deliberately limited to the default action and the four tracked marker actions
`use`, `status`, `process`, and `verify`. A non-default selector must resolve to the corresponding
marker inside the adapter; same-size external files are rejected. It accepts no parameters or
trailing arguments. Use
`harness.ps1` for typed parameters or any other declared action. Never feed untrusted or
data-controlled text through a `.cmd` launcher; Windows parses batch input before the script can
validate it.

The repository-level `reserve.cmd` always returns `BLOCK`. Use `reserve.ps1` for management
commands. This asymmetry preserves the familiar project commands without pretending batch files are
a closed general-purpose argument transport.

## Requirements

- Python 3.11 or later;
- PowerShell 7 (`pwsh`) for Windows launchers and PowerShell actions;
- Git only when repository state, clean-worktree constraints, or ignore checks are needed.

The Python runtime has no third-party runtime dependencies. Schema conformance tooling may use the
development-only `jsonschema` package.

Optional natural-language intent proposal requires a separately installed Ollama service with
`gpt-oss:20b`. Harness Reserve never installs or downloads Ollama or a model, never changes the
fixed `127.0.0.1:11434` endpoint or model, and never falls back to a hosted or paid API. OpenAI's
[Ollama guide for gpt-oss](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama)
describes the manual installation and pull flow and recommends at least 16 GB of VRAM or unified
memory for `gpt-oss:20b`; CPU offload can be slower. Ollama is absent from the current validation
host, whose discrete GPU has 4 GB of VRAM, so provider behavior is mock-tested only. No live
inference, performance, or local-provider privacy claim has been established on that host.

PowerShell execution policy is respected; the runtime does not bypass it. If a trusted downloaded
archive carries Windows Mark-of-the-Web metadata, review the checkout and unblock only that checkout
from its root:

```powershell
Get-ChildItem -LiteralPath (Resolve-Path .) -Recurse -File | Unblock-File
```

Do not weaken machine-wide execution policy to run Harness Reserve.

## Repository map

- `src/harness_reserve/` — dependency-free Python reference runtime;
- `schemas/` — strict JSON contracts;
- `src/harness_reserve/resources/project-adapter/` — packaged fail-closed adapter template;
- `examples/minimal-python-project/` — executable synthetic reference integration;
- `docs/` — design, contract, security, adoption, and protocol guidance;
- `tests/` — discovery, policy, execution, privacy, Windows, and failure-mode tests;
- `VALIDATION.md` — exact current technical evidence and remaining validation limits;
- `SCAFFOLD_MANIFEST.json` — SHA-256 inventory of packaged source files.

`AGENTS.md` is the short map. Follow its read order for progressive disclosure.

## Try the reference example

From PowerShell 7 at the repository root:

```powershell
.\reserve.ps1 --project-root .\examples\minimal-python-project validate
.\reserve.ps1 --project-root .\examples\minimal-python-project doctor
.\reserve.ps1 --project-root .\examples\minimal-python-project list
.\reserve.ps1 --project-root .\examples\minimal-python-project run
.\reserve.ps1 --project-root .\examples\minimal-python-project run status
.\reserve.ps1 --project-root .\examples\minimal-python-project run process --params-json '{"item":"sample","open-after":true}'
.\reserve.ps1 --project-root .\examples\minimal-python-project run verify
.\reserve.ps1 --project-root .\examples\minimal-python-project latest
.\reserve.ps1 --project-root .\examples\minimal-python-project handoff
```

The tracked reference intent selects only read-only `status` and is dry-run by default:

```powershell
.\reserve.ps1 --project-root .\examples\minimal-python-project dispatch-intent .\examples\minimal-python-project\status.intent.json
.\reserve.ps1 --project-root .\examples\minimal-python-project dispatch-intent .\examples\minimal-python-project\status.intent.json --execute
```

With a manually installed and running Ollama `gpt-oss:20b`, the optional reference proposer adds a
natural-language first step:

```powershell
.\reserve.ps1 --project-root .\examples\minimal-python-project propose-intent --request "Report readiness."
```

That command makes one fixed-loopback request, writes a validated intent below
`.harness-reserve/state/intents/`, prints a dry-run plan, and executes nothing. Inspect the printed
intent path, then use the existing dispatcher in a separate command:

```powershell
.\reserve.ps1 --project-root .\examples\minimal-python-project dispatch-intent <printed-intent-path>
.\reserve.ps1 --project-root .\examples\minimal-python-project dispatch-intent <printed-intent-path> --execute
```

`propose-intent` has no `--execute`, confirmation, endpoint, model, credential, or fallback option.
The request text is sent to the local Ollama process and may remain in PowerShell history or
provider-managed logs; do not place secrets or private source text in it. Harness Reserve does not
store the raw request, provider response, or model reasoning in its intent, receipt, or handoff.
See `docs/LOCAL_MODEL_PROTOCOL.md` for the exact eligibility, size, timeout, and privacy boundaries.

The example's `serve-private` action is synthetic: it does not start a server. Its
`network: private-lan` declaration exists to prove the deterministic confirmation floor:

```powershell
.\reserve.ps1 --project-root .\examples\minimal-python-project run serve-private --params-json '{"minutes":5}'
.\reserve.ps1 --project-root .\examples\minimal-python-project run serve-private --params-json '{"minutes":5}' --confirm
```

The first command is expected to block; the confirmed command may execute the synthetic action.
See `VALIDATION.md` for current native-Windows results rather than inferring them from these examples.

From a POSIX shell:

```text
PYTHONPATH=src python -m harness_reserve --project-root examples/minimal-python-project list
PYTHONPATH=src python -m harness_reserve --project-root examples/minimal-python-project run status
```

In JSON mode, executed action stdout and stderr are suppressed from CLI output so stdout remains one
privacy-minimized JSON document. Non-JSON mode displays action output to the local caller. Neither
mode stores that output in the receipt.

## Adopt it in another repository

```powershell
.\reserve.ps1 init `
    --target C:\Projects\my-harness `
    --project-id my-harness `
    --display-name "My Harness"
```

Initialization refuses overwrite and symlink/reparse ancestors within adapter destinations. The
generated `status` action reports `DEGRADED` with project state `UNCONFIGURED`; the `use`, `process`,
and `verify` stubs return `BLOCK`. Every template action is human-only until an adopter deliberately
reviews and enables model invocation.

Replace each stub with thin delegation to an existing tracked project script. Merge the supplied
ignore rules for state and candidates, then run `validate` and `doctor`. Do not duplicate a working
project pipeline merely to satisfy the shared interface.

Read next:

1. `ARCHITECTURE.md`
2. `docs/DESIGN.md`
3. `docs/CONTRACT.md`
4. `docs/SECURITY_MODEL.md`
5. `docs/ADOPTION.md`
6. `docs/ADAPTER_PATTERNS.md`
7. `docs/LOCAL_MODEL_PROTOCOL.md`

## Evidence and authority boundary

Harness Reserve validates declared metadata and dispatches trusted project entrypoints without a
shell. It is not an operating-system sandbox and cannot enforce an action's claimed filesystem or
network authority.

Receipts and handoffs omit command output, file contents, Git diffs, and sensitive parameter values,
but they are local operational artifacts, not publication-ready reports. They include project
identity and may include an absolute local repository path, branch, commit, and project-supplied
fields marked safe. Review them before sharing.

A technical `PASS` proves only the bounded action and contract checks represented by its evidence.
It does not imply human acceptance, semantic approval, ATTUNE lifecycle advancement, release
authorization, publication, or deployment.

## Licensing

Harness Reserve is open source under the [MIT License](LICENSE). The public source repository is
[josephbartlett/harness-reserve](https://github.com/josephbartlett/harness-reserve). Contributions
are welcome through the focused, contract-conscious process in [CONTRIBUTING.md](CONTRIBUTING.md).
Technical validation still does not authorize a release, package publication, deployment, or
project adoption.
