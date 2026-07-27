# Contract reference

Contract version 1 is a closed, fail-closed JSON contract. The Python runtime is authoritative for
canonical filesystem checks and execution policy; the schemas provide portable structural
validation.

## 1. Strict JSON

Runtime-loaded JSON rejects:

- malformed syntax;
- duplicate object keys;
- `NaN`, `Infinity`, and `-Infinity`;
- non-object top-level values where an object is required;
- unknown fields at each closed contract layer.

Unknown manifest fields are allowed only inside explicit `extensions` objects. Contract version 1
has extension objects only at the manifest, action, and constraint layers. Action results also have
an explicit `extensions` object. Receipts, latest pointers, intents, handoffs, evidence records, and
candidate manifests have exact shapes.

## 2. Project manifest

The tracked project manifest is:

```text
.harness-reserve/operator.json
```

A minimal shape is:

```json
{
  "contract_version": 1,
  "project": {
    "id": "example-project",
    "display_name": "Example Project"
  },
  "default_action": "status",
  "actions": {
    "status": {
      "description": "Report aggregate readiness.",
      "runner": "python",
      "entrypoint": ".harness-reserve/actions/status.py",
      "authority": {
        "filesystem": "read-only",
        "network": "none",
        "git": "read",
        "external_systems": "none",
        "secrets": "none",
        "semantic_authority": "none"
      }
    }
  }
}
```

Validation also requires the referenced entrypoint and working directory to exist.

Required top-level fields are `contract_version`, `project`, `default_action`, and a non-empty
`actions` object. Optional top-level fields are `$schema`, `runtime`, `state`, `constraints`, and
`extensions`.

`project.id` is a stable identifier matching:

```text
^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$
```

`project.display_name` is a non-empty single line. Optional `project.description` is a string.
Optional `project.platforms` is a non-empty, duplicate-free array containing `windows`, `linux`, or
`macos`; it defaults to `["windows"]`.

Action ids match:

```text
^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$
```

`default_action` must name one declared action. `runtime.minimum_version`, when present, uses
`MAJOR.MINOR.PATCH`; the runtime rejects a requirement newer than itself.

## 3. State and path contract

Defaults are:

```json
{
  "state": {
    "directory": ".harness-reserve/state",
    "handoff_directory": ".harness-reserve/state/handoffs"
  }
}
```

`state.directory` must resolve at or below `.harness-reserve/state`. The handoff directory must
resolve at or below the selected state directory. Merely resolving somewhere else inside the
project is not sufficient.

The optional reference proposer stores validated intents below the separate fixed reserved
directory:

```text
.harness-reserve/state/intents/
```

This path does not follow a custom `state.directory`. It remains inside the reserved state root and
must be ignored by the adopting repository. Proposal blocks before provider access unless Git
verifies the directory as ignored.

Entrypoints, working directories, state, handoff, receipt pointers, and evidence paths use portable
project-relative path text. The runtime rejects:

- absolute, drive-relative, rooted, UNC, extended, or device paths;
- parent traversal;
- NTFS alternate-data-stream syntax and any other colon;
- null characters;
- Windows components ending in a dot or space;
- reserved Windows device basenames such as `CON`, `NUL`, `COM1`, and `LPT1`;
- a path whose canonical resolution escapes the project root.

Existing symbolic-link and reparse-point targets participate in canonical resolution. JSON Schema
cannot prove filesystem containment by itself; consumers that execute actions must apply the runtime
checks. Adapter initialization additionally refuses symlink or reparse-point ancestors.

## 4. Action definition

Every action requires:

- a non-empty `description`;
- one `runner`;
- a repository-relative `entrypoint`;
- all six explicit authority fields.

Optional fields and runtime defaults are:

| Field | Default |
|---|---|
| `working_directory` | `.` |
| `fixed_args` | `[]` |
| `parameters` | `{}` |
| `environment` | `{}` |
| `timeout_seconds` | `3600` |
| `confirmation` | `{"mode":"none","prompt":"Confirm this action."}` |
| `model_invocable` | `false` |

`timeout_seconds` is an integer from 1 through 86400. Fixed arguments and environment values are
tracked literal strings, not model input. Environment names use
`^[A-Za-z_][A-Za-z0-9_]*$`. The child otherwise inherits the current process environment.

### Runners

- `python` — the current Python interpreter with `-X utf8 -B` plus the exact entrypoint, keeping
  text behavior explicit and suppressing bytecode in the adopting project;
- `powershell` — PowerShell 7 with `-NoLogo -NoProfile -NonInteractive -File` and the exact
  entrypoint;
- `executable` — the exact repository-relative native executable.

The executable runner rejects known script and document suffixes on every platform. On Windows it
accepts only `.exe` or `.com`. On Linux and other supported non-macOS POSIX hosts it requires ELF
magic; on macOS it requires Mach-O or fat Mach-O magic. The runtime rechecks this immediately before
process construction. Batch, shell, PowerShell, Python, JavaScript, VBScript, shortcut, URL, and
similar files cannot be smuggled through `runner: executable`.

There is no shell runner, command-string field, caller-supplied positional argument tail,
environment expansion in paths, or arbitrary executable selection. Process construction uses an
argument array with `shell=False`.

### Authority

Every action declares exactly one value in every dimension:

| Dimension | Values |
|---|---|
| `filesystem` | `read-only`, `derived-only`, `workspace-write`, `unrestricted-project` |
| `network` | `none`, `loopback`, `private-lan`, `internet` |
| `git` | `none`, `read`, `write`, `publish` |
| `external_systems` | `none`, `read`, `write` |
| `secrets` | `none`, `read` |
| `semantic_authority` | `none`, `candidate`, `canonical` |

There are no implicit authority defaults. These labels drive policy and review; they are not an OS
sandbox.

## 5. Typed parameters

Parameter names are manifest keys, not command fragments. Each parameter maps to one non-empty flag
token; flags must be unique within an action and cannot contain whitespace or null characters.
Unknown supplied parameters fail.

Supported types are:

- `boolean` — emits the flag only when true;
- `string` — at most 4096 characters, with optional full-match regular expression;
- `integer` — optional inclusive `minimum` and `maximum`;
- `enum` — one member of a non-empty, duplicate-free string array.

A parameter may be `required`, have a `default`, be marked `sensitive`, and include an optional
string `description`. Missing required parameters without defaults fail. Invalid types, patterns,
enum members, and bounds fail before process launch. Eligible parameter descriptions are visible to
the optional local-model provider.

Sensitive values are passed to the trusted project action but replaced with `<redacted>` in
receipts, dry-run plans, and command previews. A sensitive boolean does not reveal whether its flag
was present in a preview. Redaction does not hide a value from the child process, local process
inspection, inherited environment, or action output.

Parameters are supplied as a JSON object:

```powershell
.\reserve.ps1 --project-root C:\Projects\example run process `
    --params-json '{"minutes":30,"open-after":true}'
```

`--params-json @path` loads the object from a human-selected JSON file.

## 6. Confirmation and Git constraints

Manifest confirmation modes are:

- `none` — no project-specific confirmation;
- `explicit` — require `--confirm`;
- `phrase` — require exact `--confirmation-text`.

Regardless of manifest preference, the runtime requires deterministic human confirmation for:

- `network: private-lan` or `internet`;
- `git: write` or `publish`;
- `external_systems: write`;
- `secrets: read`;
- `semantic_authority: canonical`;
- `filesystem: unrestricted-project`.

With phrase mode, the exact declared phrase is required. Otherwise the hard floor requires
`--confirm`. This floor cannot be weakened by a manifest.

`constraints.require_clean_git_for` names actions that block when Git state is unavailable or the
exact project worktree is dirty. `constraints.forbid_model_actions_when_dirty` defaults to true and
blocks model intent when a dirty count is known to be nonzero.

Direct human-run confirmation is checked before Git inspection. Git reads use a sanitized control
environment and disable configured fsmonitor and untracked-cache helpers.

## 7. Local-model intent

An operator intent has exactly six required fields:

```json
{
  "contract_version": 1,
  "project_id": "example-project",
  "action": "status",
  "parameters": {},
  "reason": "The user asked for aggregate readiness.",
  "confidence": 0.98
}
```

The project id must match, the action and parameters must validate, `reason` must be non-empty and at
most 1000 characters, and `confidence` must be numeric from 0 through 1.

An intent-selected action must be explicitly `model_invocable` and stay within this ceiling:

| Dimension | Model-allowed values |
|---|---|
| `filesystem` | `read-only`, `derived-only` |
| `network` | `none`, `loopback` |
| `git` | `none`, `read` |
| `external_systems` | `none` |
| `secrets` | `none` |
| `semantic_authority` | `none`, `candidate` |

Any action declaring a sensitive parameter is ineligible for model intent. Every resolved model
string or enum value, including a default, must match:

```text
^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$
```

This excludes paths, whitespace, dots, and command syntax. Confirmation cannot override any model
ceiling. `dispatch-intent` is dry-run by default; `--execute` authorizes only execution of the
already validated action. A dry run launches no project action and writes no run receipt.

### Fixed-loopback reference proposer

`propose-intent` is an optional convenience adapter layered in front of the same intent validator.
It is not part of the action manifest and does not change the six-field operator-intent schema.

Its provider connection is fixed:

| Setting | Value |
|---|---|
| host | `127.0.0.1` |
| port | `11434` |
| path | `/v1/chat/completions` |
| model | `gpt-oss:20b` |
| stream | `false` |
| attempts | one |

There is no command-line or manifest field for another host, port, path, model, credential, tool,
retry, or hosted fallback. The request is an unauthenticated loopback HTTP request using the
standard-library client. The system message begins with `Reasoning: low`; reasoning fields are not
part of the accepted selector or saved intent.

Before transport, the proposer constructs a catalog containing only confirmation-free actions that
pass `model_invocable`, model-authority, sensitive-parameter, resolved-default, and configured
known-dirty checks. It sends the human request plus eligible action descriptions and reduced
parameter type, required, description, enum/bound, and pattern data. It does not send project id,
entrypoint, working directory, fixed arguments, flags, environment, authority metadata, Git
metadata, receipts, or non-manifest repository files.
Descriptions, enum values, and patterns in that reduced catalog are still trusted manifest
content. They are not scrubbed for private prose or path-like text and must be reviewed before an
action becomes model-invocable.

The internal provider content has one of two exact shapes:

```json
{"decision":"select","action":"status","parameters":{},"confidence":0.93}
```

```json
{"decision":"refuse"}
```

This select-or-refuse object is internal adapter data, not a new public schema. A selection must name
one action from the transmitted catalog. Harness Reserve injects `contract_version`, `project_id`,
and a fixed aggregate `reason`, then validates the complete public intent through the ordinary
deterministic intent policy. A refusal or any invalid provider response returns `BLOCK` and creates
no intent. Provider tool or function calls are invalid even when message content is also present.

Provider proposal limits are:

| Item | Limit |
|---|---:|
| non-empty request text | 2000 characters |
| eligible catalog | 32 KiB |
| request envelope | 64 KiB |
| response envelope | 64 KiB |
| response message content | 16 KiB |
| total provider-call timeout | 5–900 seconds; default 300 |

The request and all JSON must be valid UTF-8; request nulls, duplicate JSON keys, and non-finite
numbers fail closed. A successful selection is written with collision-safe no-overwrite semantics
to:

```text
.harness-reserve/state/intents/<UTC timestamp>-<random>.intent.json
```

The destination must be verifiably ignored, contain no existing symlink/reparse component, and stay
inside the project root. It is re-resolved after the provider wait and before publication so a
changed or unverifiable directory blocks rather than receiving the intent.

The command returns the ordinary redacted dry-run action plan plus provider, model, and relative
intent path. It always reports `dry_run: true` and `executed: false`, launches no action, creates no
run receipt, and does not update `latest.json`.

Harness Reserve does not store or echo the raw user request, provider response, or provider
reasoning. It does store the validated selected action, non-sensitive parameters, confidence, and
fixed reason in the local intent. Shell history and provider-managed Ollama logs are outside this
contract.

## 8. Action result

The runtime supplies `HARNESS_RESERVE_RESULT_PATH`. A project action may write:

```json
{
  "contract_version": 1,
  "outcome": "PASS",
  "safe_summary": "The aggregate readiness check completed.",
  "project_state": "READY",
  "warnings": [],
  "evidence": [
    {
      "kind": "receipt",
      "label": "Synthetic readiness receipt",
      "path": ".local/readiness.json",
      "safe_to_share": false
    }
  ],
  "next_action": "status"
}
```

Only `contract_version` and `outcome` are required. Defaults are project state `UNKNOWN`, empty
warnings and evidence, and no next action.

Unknown fields fail except within `extensions`. `safe_summary`, warnings, evidence labels, and
`next_action` are project-supplied aggregate data; summaries and individual warnings are bounded to
1000 characters. Evidence paths must remain within the project and are normalized. An optional
digest is exactly 64 lowercase hexadecimal characters. The runtime validates its format but does
not prove that it matches the referenced file.

`safe_to_share: true` is a project assertion, not content inspection. False evidence is counted but
not copied into the generic handoff. `next_action` is advisory text; it is never executed and grants
no authority.

## 9. Exit and outcome reconciliation

| Process exit | Process outcome |
|---:|---|
| 0 | `PASS` |
| 10 | `DEGRADED` |
| 20 | `BLOCK` |
| any other nonzero | `ERROR` |
| timeout | `ERROR` |

Severity is:

```text
PASS < DEGRADED < BLOCK < ERROR
```

The effective outcome is the more severe of the process outcome and a valid action result. When the
process is more severe, project-supplied summary, state, evidence, and next action are suppressed.
A missing action result is not itself an error, but leaves aggregate project state `UNKNOWN`. A
present malformed result produces `ERROR`.

Observed manifest or entrypoint change or disappearance during execution also produces `ERROR` and
suppresses the project result. Timeout tree termination is best effort and may add a warning.

## 10. Receipt, latest pointer, and handoff

Every executed action gets a unique run id and writes one exact aggregate receipt containing:

- contract/runtime versions, run id, and timestamps;
- project id, display name, and absolute local project root;
- action, invocation origin, and redacted parameters;
- declared authority;
- runner, relative entrypoint and working directory, exit code, timeout, timed-out flag, and outcome;
- manifest and entrypoint SHA-256 before and after execution, plus changed flags;
- Git availability, repository identity, branch, commit, and dirty path count before and after;
- project state, safe summary, warnings, safe evidence and private/safe/total counts;
- action-result presence and validity flags;
- explicit false assertions for stdout, stderr, Git-diff, and file-content storage.

The receipt never stores process stdout, stderr, Git diffs, or file contents. JSON CLI mode also
suppresses action output from the terminal response; ordinary mode displays it locally.

Each receipt is atomically replaced into:

```text
.harness-reserve/state/runs/<run-id>/receipt.json
```

The on-disk `latest.json` contains only:

```json
{
  "contract_version": 1,
  "run_id": "20260726T120000Z-0123abcd",
  "receipt_path": ".harness-reserve/state/runs/20260726T120000Z-0123abcd/receipt.json",
  "receipt_sha256": "0000000000000000000000000000000000000000000000000000000000000000"
}
```

Loading latest requires the exact expected path, matching digest, exact receipt shape, matching run
id, and matching current project id and root. These are consistency checks, not a signature.

`handoff` requires a valid latest receipt, records current aggregate Git metadata, binds the receipt
path and digest, and emits JSON and Markdown below the configured handoff directory. It includes
static authority boundaries and no private action output. Project-supplied safe fields remain
untrusted assertions and must be reviewed before sharing or treating them as instructions.

Receipts and handoffs are local operational artifacts. Their project paths, repository identity,
branch, commit, and safe fields may still be sensitive.

## 11. Runtime CLI

Global options are placed before the command:

```text
harness-reserve [--project-root PATH] [--manifest PATH] [--json] <command>
harness-reserve --version
```

Commands are:

```text
list
validate
doctor
describe <action>
run [action] [--params-json JSON|@file] [--confirm] [--confirmation-text TEXT] [--dry-run]
latest
handoff [--print-packet]
dispatch-intent <file> [--execute] [--confirm] [--confirmation-text TEXT]
propose-intent --request TEXT [--timeout-seconds INTEGER]
init --target <project> --project-id <id> --display-name <name>
```

`latest` and `handoff` require an existing valid run. Direct discovery starts at the supplied project
root or manifest, or walks upward from the current directory.

`propose-intent` never executes an action and accepts no `--execute`, `--confirm`,
`--confirmation-text`, `--model`, or `--endpoint` option. To act on the resulting file, the human
uses `dispatch-intent` separately; that command reloads current project state and reapplies intent
policy before its default dry run or explicit `--execute`.

On Windows, `reserve.ps1` is the management entrypoint. `reserve.cmd` always blocks. A project
adapter provides:

```text
harness.cmd [use|status|process|verify]  fixed tracked-marker convenience only
harness.ps1 [action] [runtime run options]  full declared project action surface
```

The project wrapper always enters through `run`, so management command names cannot collide with
project actions.

CLI exit codes are 0 for `PASS`, 10 for `DEGRADED`, 20 for `BLOCK`, and 1 for `ERROR`. Argument-parser
usage errors return 2.

## 12. Compatibility and authority

Contract-version-1 shapes are closed. Adding a manifest, action-result, receipt, latest-pointer,
intent, or handoff field is incompatible unless explicit version handling is defined. Security
validation may become stricter where it enforces an already stated invariant; weakening path,
command, confirmation, receipt-integrity, or model-authority rules requires a deliberate contract
decision.

The internal fixed-provider select-or-refuse object and provider HTTP envelope are implementation
details rather than contract-version-1 artifacts. Adding the proposal adapter therefore does not
change the manifest or operator-intent schema.

Runtime version and contract version are separate. Runtime releases may fix implementation defects
without changing the contract; a project may declare a minimum runtime version.

A contract-valid technical `PASS` is not human acceptance, semantic approval, release authorization,
ATTUNE promotion, publication, deployment, or permission to commit or push.
