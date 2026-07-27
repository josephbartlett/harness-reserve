# Harness Reserve design

## 1. Problem statement

A mature harness usually contains more than a coding agent. It contains application launchers,
local tools, ingestion and synchronization scripts, tests, status checks, source-of-truth documents,
privacy rules, receipts, and repeatable operating workflows. When hosted Codex is unavailable, those
assets do not disappear. The missing component is often a reliable way for the human operator to
invoke them without remembering every project-specific command or pretending that a weaker local
model can safely replace the primary coding agent.

Harness Reserve provides that missing operating layer.

Its target is not autonomous development. Its target is graceful degradation:

- open and use an existing local application;
- run known foreground processing or synchronization tools;
- inspect aggregate readiness;
- run ordinary verification;
- preserve evidence and continuation state;
- optionally let a local model select one safe action;
- define a project-owned protocol for staging model-dependent candidate work without silently
  changing canonical state.

## 2. Non-goals

Harness Reserve is not:

- another general-purpose agent framework;
- a replacement for Codex, ATTUNE, or a repository's own orchestrator;
- a package manager;
- a background daemon or file watcher;
- an operating-system sandbox;
- a deployment or publication system;
- a universal semantic interpreter;
- a reason to duplicate working project scripts;
- a hidden API fallback that can generate unexpected cost.

A project should remain usable if Harness Reserve is removed. The project-owned scripts are the
capability. Harness Reserve is a consistent, inspectable facade over them.

## 3. Design principles

### 3.1 Repository knowledge is authoritative

The adopting repository owns its manifest and adapters. The runtime does not rely on chat history,
model memory, or a central registry to know how a project works.

The design follows the repository-legibility lessons described in OpenAI's
[Harness Engineering](https://openai.com/index/harness-engineering/) article: keep `AGENTS.md`
short, use progressive disclosure, make the app and its evidence directly operable, and encode
important boundaries mechanically rather than only in prose.

### 3.2 A model is not required for known operations

If a task can be represented as a stable action such as `use`, `status`, `process`, or `verify`, the
human should be able to execute it directly. A local model may improve convenience by selecting an
action, but it is never the only route to that action.

### 3.3 Project behavior stays project-owned

The shared runtime never learns domain logic. An audio-authorship adapter may call its continuation pipeline. A web application adapter may start a local server. A hardware project may collect sensor
data. A healthcare integration project may run synthetic-message validation. Each project chooses
its own action names and implementation while conforming to the same invocation and receipt
contracts.

### 3.4 The dispatcher is closed

The manifest declares exact entry points and exact parameter shapes. The runtime rejects:

- duplicate JSON keys and non-finite JSON numbers;
- arbitrary command strings;
- shell fragments;
- unknown actions;
- unknown parameters;
- model-provided executable paths;
- absolute entrypoint paths;
- path traversal outside the project root;
- unsupported runners;
- undeclared environment variables;
- unconfirmed sensitive authority.

Repository paths also reject Windows drive/root/UNC forms, device and extended forms, alternate
streams and other colons, parent traversal, reserved device names, and components ending in a dot or
space. Existing symlink/reparse targets are canonicalized before containment checks. The Python
runtime uses `subprocess` with `shell=False`; on Windows the executable runner accepts only `.exe`
or `.com`, supported POSIX hosts require ELF or Mach-O native magic, and script/document suffixes
are rejected on every host.

### 3.5 Authority is visible and conservative

Every action declares six authority dimensions:

- filesystem;
- network;
- Git;
- external systems;
- secrets;
- semantic authority.

These declarations are part of review, UI, confirmation, and receipts. They are not a substitute for
an OS sandbox. The runtime imposes a hard confirmation floor for sensitive combinations even when a
manifest says confirmation is unnecessary.

All six authority fields are explicit; there are no implicit defaults.

### 3.6 Evidence is aggregate by default

The runtime records action id, exit code, outcome, hashes, timing, Git branch/commit/counts, safe
project state, and explicitly share-safe evidence. It does not store:

- stdout;
- stderr;
- file contents;
- Git diffs;
- raw transcripts;
- secrets;
- sensitive parameter values.

Projects can still maintain their own private logs in their existing locations. Harness Reserve does
not copy those logs into the shared receipt. `safe_summary`, warnings, next actions, and
`safe_to_share` evidence remain project assertions: the runtime validates their shape, not whether
their content is truthful or secret-free. Receipts and handoffs are minimized local artifacts, not
anonymized or automatically publication-safe.

### 3.7 Degraded is a valid state

A mechanical pipeline may finish while semantic interpretation remains pending. A local app may be
usable while one optional integration is offline. These conditions should be represented honestly as
`DEGRADED`, `STALE`, or `UNKNOWN`, not collapsed into false `PASS` or generic failure.

### 3.8 Promotion is separate from generation

The shared schema describes how a project may bind candidate inputs and outputs under an ignored
candidate directory. Candidate generation, deterministic semantic validation, human review, and
promotion are project-owned; the core does not implement a generic generator or promoter. Any
promotion to canonical state is a distinct action with validation, human review, and rollback
evidence.

## 4. Architecture

### 4.1 Shared runtime

The shared runtime is a small dependency-free Python package. It is responsible for:

1. project discovery;
2. manifest validation;
3. parameter validation;
4. path containment;
5. confirmation policy;
6. exact process construction;
7. execution and timeout handling;
8. action-result validation;
9. aggregate receipt generation;
10. local-model intent validation;
11. an optional fixed-loopback, proposal-only local-model adapter;
12. model-neutral continuation packets.

### 4.2 Project adapter

An adopting project adds:

```text
.harness-reserve/
  operator.json
  actions/
    ... project-owned thin adapters ...
harness.cmd
harness.ps1
```

The adapter should be thin. A good action script is usually ten to sixty lines that:

1. confirms project-specific preconditions;
2. invokes an existing tracked script or executable;
3. maps its outcome to PASS, DEGRADED, BLOCK, or ERROR;
4. writes an aggregate `action-result.json` to the path supplied by the runtime.

It should not recreate the underlying pipeline.

### 4.3 Project launcher

The project launcher resolves the shared runtime in this order:

1. `HARNESS_RESERVE_HOME`;
2. project-local `.tools/harness-reserve` checkout or submodule;
3. a sibling `harness-reserve` checkout;
4. a trusted installed `harness-reserve` application on `PATH`.

This allows a project to reference a centrally maintained runtime without copying it. The installed
application is a fallback runtime reference, not a checkout. Projects may pin the shared runtime
through a Git submodule, a trusted Python environment, a dependency-management convention, or a
documented version policy. The starter does not force one strategy.

### 4.4 State and receipts

The default state layout is:

```text
.harness-reserve/state/
  latest.json
  runs/
    <run-id>/
      action-result.json
      receipt.json
  intents/
    <timestamp>-<random>.intent.json
  handoffs/
    handoff-<timestamp>.json
    handoff-<timestamp>.md
```

The runtime creates a unique run directory before execution and exposes it through environment
variables. The project action may write only the declared action-result document into the supplied
path, although its existing pipeline may write its normal project-owned outputs elsewhere.

The manifest state directory must remain at or below `.harness-reserve/state`, and the handoff
directory must remain below that state directory. `latest.json` is a minimal pointer containing
contract version, run id, exact repository-relative receipt path, and receipt SHA-256. Loading latest
or building a handoff revalidates that pointer, digest, receipt shape, project identity, and run
identity.

Receipts bind pre-execution manifest and entrypoint hashes plus nullable post-execution hashes and
change flags. Observed mutation or deletion forces ERROR and suppresses the project result. This is
inconsistency detection, not a signature, rollback mechanism, or race-proof isolation boundary.

Validated provider proposals are stored separately below the fixed reserved
`.harness-reserve/state/intents/` directory. They are ordinary input documents for later dispatch,
not action runs, receipts, or grants of execution authority.

### 4.5 Environment contract

Actions receive:

```text
HARNESS_RESERVE_RUNTIME_VERSION
HARNESS_RESERVE_PROJECT_ROOT
HARNESS_RESERVE_PROJECT_ID
HARNESS_RESERVE_ACTION
HARNESS_RESERVE_RUN_ID
HARNESS_RESERVE_RUN_DIR
HARNESS_RESERVE_RESULT_PATH
HARNESS_RESERVE_INVOKED_BY
```

These values are runtime-owned. Project manifests may add fixed literal environment variables, but
cannot inject a model-generated environment map.

## 5. Action model

### 5.1 Common action families

The shared contract does not require fixed action names, but most projects will benefit from some of
these:

| Action family | Purpose | Typical authority |
|---|---|---|
| `status` | Aggregate readiness and stale-state classification | read-only |
| `use` | Open or launch ordinary local experience | derived-only, loopback |
| `process` | Run known foreground ingestion/sync/build tools | derived-only |
| `review` | Open a human review package | read-only |
| `verify` | Run ordinary non-destructive tests | read-only |
| `serve-private` | Bounded private-LAN access | private-lan, explicit confirmation |
| `candidate` | Generate model-dependent candidate artifacts | derived-only, semantic candidate |
| `promote` | Promote validated candidate to canonical state | workspace-write, canonical, confirmation |

A project should expose the smallest useful set rather than forcing all of them.
`candidate` and `promote` are illustrative project-owned actions, not built-in runtime commands.

### 5.2 Parameter binding

Action parameters are typed and mapped to one declared flag. Supported MVP types are:

- boolean switch;
- string with optional regular expression;
- integer with minimum and maximum;
- enum with fixed values.

The runtime builds an argument array. It never joins parameters into a command string. Positional
arguments and generic passthrough are intentionally absent from contract version 1.

### 5.3 Exit codes and outcomes

The reference convention is:

| Exit code | Outcome |
|---:|---|
| 0 | PASS |
| 10 | DEGRADED |
| 20 | BLOCK |
| any other nonzero | ERROR |

An action-result document may declare an equal or more conservative outcome. The runtime never lets a
project result turn a nonzero process failure into PASS.

### 5.4 Project state

Actions may report:

- `READY`;
- `DEGRADED`;
- `BLOCKED`;
- `STALE`;
- `UNCONFIGURED`;
- `UNKNOWN`.

Outcome describes the action invocation. Project state describes the broader project condition. A
`status` action can PASS while accurately reporting `DEGRADED` project state.

## 6. Operator plane

The operator plane is the foundation and should ship first.

Human flow:

```text
harness.cmd                 -> run default project action
harness.cmd status          -> run declared status action
harness.cmd process         -> run declared process action
harness.cmd verify          -> run declared verify action
```

The generated CMD surface is fixed to those argument-free conveniences and uses exact tracked
marker identity after a metadata-only size gate. Same-size external paths are rejected; equivalent
paths to the actual marker may resolve to the same fixed action. Typed or data-controlled inputs and
other actions go through `harness.ps1`. Windows performs initial batch parsing before the script can
validate input, so CMD is not an untrusted-data boundary.

Management flow:

```text
reserve.ps1 --project-root <repo> list
reserve.ps1 --project-root <repo> validate
reserve.ps1 --project-root <repo> doctor
reserve.ps1 --project-root <repo> describe <action>
reserve.ps1 --project-root <repo> latest
reserve.ps1 --project-root <repo> handoff
```

The root `reserve.cmd` always returns BLOCK 20 instead of forwarding a raw batch argument tail.
Management command names cannot collide with project actions because project PowerShell wrappers
always enter through `run`.

## 7. Intent plane

The intent plane keeps proposal and execution mechanically separate. The dispatcher remains
provider-independent and continues to accept any exact `operator-intent.schema.json` document. The
optional reference proposer is deliberately narrower: it makes one HTTP request to Ollama at the
literal loopback address `127.0.0.1:11434`, uses only `gpt-oss:20b`, and can create only a validated
dry-run intent.

The proposer receives a human request and constructs a reduced catalog containing only actions that
are:

- explicitly `model_invocable`;
- inside the existing model authority ceiling;
- free of sensitive parameters;
- free of manifest or hard-floor confirmation;
- not blocked by a known nonzero dirty count when the project enables the model-dirty gate.

The provider sees the request and eligible action descriptions plus reduced typed parameter
contracts. It does not receive project identity, executable or working-directory paths, fixed
arguments, flags, environment values, authority metadata, hidden or ineligible actions, receipts,
Git metadata, or non-manifest repository files through this adapter. Eligible action and parameter
descriptions, enum values, and regex patterns are trusted manifest content sent to the provider;
adopters must keep that catalog metadata appropriate for local-provider disclosure.

The internal provider response is either:

```json
{"decision":"select","action":"status","parameters":{},"confidence":0.93}
```

or:

```json
{"decision":"refuse"}
```

That provider shape is not the public operator-intent contract. Exact fields are enforced; malformed
JSON, duplicate keys, non-finite numbers, prose, tool or function calls, unknown fields, missing
fields, unknown actions, and invalid parameters fail closed. Harness Reserve supplies the contract
version, matching project id, and a fixed aggregate reason rather than trusting provider text for
those fields.

The resulting stored intent still has the public six-field shape:

Example:

```json
{
  "contract_version": 1,
  "project_id": "example",
  "action": "process",
  "parameters": {
    "open-after": true
  },
  "reason": "Selected by the fixed local gpt-oss proposal adapter after deterministic validation.",
  "confidence": 0.93
}
```

The proposer then asks the ordinary action runtime for a dry-run plan and atomically creates a new
intent below `.harness-reserve/state/intents/`. It never overwrites an existing intent, launches the
project action, writes a run receipt, or advances `latest.json`. The `propose-intent` command has no
execution, confirmation, model, endpoint, credential, or arbitrary provider option.

Provider I/O is bounded: requests are non-empty UTF-8 text of at most 2000 characters; the eligible
catalog is at most 32 KiB; HTTP request and response envelopes are at most 64 KiB; model content is
at most 16 KiB; and provider timeout is an integer from 5 through 900 seconds with a 300-second
default applied as a total provider-call deadline. The system prompt requests low reasoning, the
request uses `stream: false`, provider tool and function calls are rejected, one attempt is made,
and there is no hosted, paid, or other-provider fallback.

Harness Reserve does not persist or echo the raw request, response body, or provider reasoning. The
stored action, non-sensitive parameters, confidence, and fixed reason remain local data. The
request may still appear in shell history, and Ollama may keep provider-managed logs outside
Harness Reserve's control.

Intent storage fails closed unless Git verifies the fixed destination as ignored. Existing
symlink/reparse ancestors are rejected, and the directory is re-resolved and rechecked after the
provider wait and again before the collision-safe no-overwrite publication.

The dispatcher, whether the intent was hand-authored or proposed:

1. rejects unknown fields;
2. requires matching project id;
3. validates action and parameters;
4. requires `model_invocable: true`;
5. applies stricter authority ceilings;
6. rejects actions declaring sensitive parameters;
7. accepts only bounded portable tokens for resolved string/enum parameters;
8. applies the configured known-dirty-worktree gate;
9. produces a dry-run by default;
10. requires `--execute` for actual invocation.

A model never sends a path or command to the executor. Human confirmation cannot raise the model
authority ceiling: private-LAN/internet, Git/external writes, secret read, unrestricted filesystem,
and canonical semantic actions are ineligible rather than merely confirmable.

The provider safety path is covered by mocked HTTP tests. Ollama is not installed on the current
validation host, and its NVIDIA RTX 3050 Ti Laptop GPU has 4 GB of VRAM. OpenAI's
[local Ollama guidance](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama)
says `gpt-oss:20b` works best with at least 16 GB of VRAM or unified memory and that CPU offload is
slower. Live inference, performance, and provider-side privacy therefore remain unverified.

## 8. Reasoning plane

Some projects need more than deterministic operations. An audio-authorship project may need semantic integration of new source. A research harness may need hypothesis ranking. A content harness may need a source-grounded
draft. These tasks can use a local model, but they are not operator actions in the same sense as
opening an app.

The schema-only, project-owned protocol uses:

```text
.harness-reserve/candidates/<kind>/<candidate-id>/
  candidate-manifest.json
  inputs/
  outputs/
  validation/
  review/
```

Rules:

- input identities are hashed and recorded;
- model/provider metadata is recorded;
- candidate outputs cannot overwrite canonical files;
- deterministic validators run before review;
- promotion is a separate project-owned action;
- promotion requires explicit human confirmation;
- rollback material is generated before canonical writes;
- a candidate can be rejected without affecting live state.

The core validates the candidate schema during repository conformance testing but does not implement
candidate generation, live source-binding verification, semantic review, or promotion.

## 9. Maintenance plane

A future local maintenance adapter may let a local coding model inspect or make a very small repair.
That is not implemented by the core runtime because arbitrary code modification cannot be expressed
as a closed action without additional isolation.

A responsible project-specific maintenance lane should require:

- disposable Git worktree;
- fixed task packet;
- no network by default;
- strict file and line budgets;
- forbidden architecture, dependency, CI, deployment, and secret changes;
- deterministic postflight diff checks;
- no commit, push, or merge;
- PASS/BLOCK packet for hosted Codex continuation.

The shared repository may later define a compatible packet format, but should not smuggle an open
shell into the operator plane.

## 10. Versioning and compatibility

Contract version and runtime version are separate.

- `contract_version` changes only for incompatible closed-contract artifact semantics.
- runtime semantic version changes for implementation evolution.
- projects declare `runtime.minimum_version`.
- the runtime rejects a manifest that requires a newer version.

Contract version 1 favors a small stable surface. New runner types, positional parameters, sandbox
integration, or signed manifests should be proposed through an explicit design decision and tested
against existing adapters.

## 11. Adoption strategy

Adopt in this order:

1. status;
2. use/open;
3. verify;
4. one foreground processing workflow;
5. aggregate handoff;
6. optional local-model intent;
7. candidate-only reasoning;
8. only then consider bounded maintenance.

This sequence produces immediate practical value without making local model quality a prerequisite.

## 12. Success criteria

Harness Reserve succeeds when:

- a user can open and operate mature local projects without hosted Codex;
- each project retains its existing launch, processing, custody, and validation behavior;
- ordinary actions are discoverable and consistent;
- unknown or sensitive requests fail closed;
- receipts improve continuation without leaking project content;
- a local model can improve convenience without becoming the executor;
- model-dependent work is visibly candidate-only;
- the shared repo stays small enough to understand, test, and replace.
