# Adapter patterns

Harness Reserve is intentionally domain-agnostic. An adapter should translate a project's existing
operating vocabulary into the shared action contract without importing domain logic into the shared
runtime.

This guide shows recurring patterns. They are examples, not mandatory action names.

The generated `harness.cmd` exposes only the default and four fixed tracked-marker actions
use/status/process/verify and accepts no trailing input. Use `harness.ps1` or the shared
`reserve.ps1` for other declared actions and typed parameters.

## 1. General adapter rule

A project adapter should be thin enough that a reviewer can answer four questions quickly:

1. What existing project entry point does this action call?
2. What authority does that entry point actually exercise?
3. What aggregate evidence proves the result?
4. What remains pending when the action cannot complete the whole workflow?

Prefer delegation:

```text
Harness Reserve action
        |
        v
thin project-owned adapter
        |
        v
existing launcher / pipeline / test / receipt
```

Avoid parallel implementations:

```text
Harness Reserve action
        |
        v
new copy of the project's launch, ingest, or verification logic
```

The second design creates two sources of truth and should be rejected.

## 2. Local web or desktop application

### Useful actions

| Action | Purpose | Typical result |
|---|---|---|
| `status` | Check dependencies, build state, and active process | READY or DEGRADED |
| `use` | Open the ordinary local application | PASS |
| `verify` | Run ordinary non-destructive checks | PASS, BLOCK, or ERROR |
| `serve-private` | Bind intentionally beyond loopback | explicit confirmation |

### Recommended behavior

`use` should call the project's normal launcher. It may build derived assets, start a loopback server,
wait for a health check, and open a browser. It should not regenerate canonical data or silently
switch from loopback to a LAN-accessible bind.

A server that binds to `127.0.0.1` may declare `network: loopback`. A server that binds to `0.0.0.0`
or a private interface must declare `network: private-lan` and receives a deterministic confirmation
gate.

### Example delegation

```powershell
& "$PSScriptRoot\..\..\scripts\Start-App.ps1" -OpenBrowser
$exitCode = $LASTEXITCODE
```

The adapter then maps the project command's evidence into the aggregate action-result contract.

## 3. Foreground ingestion or synchronization pipeline

Examples include local audio intake, image processing, document indexing, synthetic-message import,
and dataset refresh.

### Useful actions

| Action | Purpose |
|---|---|
| `status` | Compare input, processed, reviewed, and canonical identities |
| `process` | Run the existing deterministic foreground pipeline |
| `review` | Open the project-owned human review package |
| `verify` | Check custody, completeness, and ordinary invariants |

### Important distinction

Do not conflate external synchronization with project processing. If Google Drive, OneDrive, a file
share, or another program places files locally, the project action should say it processed locally
available input. It should not claim it forced or verified the external synchronization unless it
actually owns that integration.

### Honest degraded state

A mechanical pipeline can succeed while interpretation remains pending:

```text
new input discovered        PASS
source hashed               PASS
transcription/indexing      PASS
human or semantic review    PENDING
canonical semantic view     STALE
```

The action may have outcome `DEGRADED` and project state `STALE` with a safe summary such as:

```text
Mechanical processing completed. Canonical interpretation has not been refreshed for the current
input identity.
```

Do not rebuild a stale view and label it current merely so `use` can open something.

## 4. Creative, authorship, or semantic corpus

These projects need a sharper line between deterministic operation and model-dependent meaning.

### Operator-plane actions

- `status`: identify current source, transcript/index, semantic, and view bindings;
- `process`: ingest, hash, transcribe, index, or prepare review material;
- `review`: open source-linked review evidence;
- `use`: open only a proven-current canonical experience, or require an explicit stale-snapshot
  parameter;
- `verify`: run provenance and custody checks.

### Candidate-plane actions

- `candidate`: generate a proposed thought map, narrative, classification, or analysis under ignored
  candidate storage;
- `candidate-verify`: validate source references, output paths, schemas, and stale bindings;
- `promote`: separately review and atomically promote an accepted candidate.

Generation and promotion must never be the same action. A model may create a candidate but cannot
select or confirm promotion of its own work.

These are project-owned protocol patterns. The shared runtime does not implement a generic candidate
generator, semantic validator, review system, or promoter.

## 5. Hardware, sensors, and edge systems

A hardware project may expose local collection and inspection without granting device mutation by
default.

### Suggested separation

| Action | Authority |
|---|---|
| `status` | local read-only |
| `collect` | derived-only writes, local device read |
| `review` | read-only local dashboard |
| `calibrate-candidate` | candidate configuration only |
| `apply-calibration` | device/external write, explicit confirmation |
| `flash-device` | high-risk external write, human-only |

A device read is still an external-system interaction even when it is attached over USB, serial, or
Bluetooth. Label it honestly. Never make firmware flashing or actuator control model-invocable in
the generic operator plane.

Hardware adapters should include deterministic timeout, device identity, and safe shutdown behavior.
Receipts should record aggregate device identity or configuration hashes only when that information
is safe to share.

## 6. Healthcare, regulated, or sensitive-data project

Use synthetic fixtures for generic conformance and reserve real-data workflows for project-specific,
reviewed actions.

### Recommended boundaries

- `status` reports aggregate counts and readiness, not message bodies or patient data;
- `verify-synthetic` exercises the normal pipeline against synthetic or deidentified fixtures;
- real protected-data actions are human-only and declare secret/external-system authority honestly;
- no generic receipt contains payloads, identifiers, query text, file contents, or diffs;
- deployment, production writes, and publication remain outside default operator actions;
- inherited environment variables are treated as potentially secret-bearing.

Harness Reserve does not make an action HIPAA-compliant, safe for PHI, or isolated. Those properties
must come from the adopting project's controls, environment, and review.

## 7. Build, test, and packaging project

### Useful actions

- `status`: dependency and artifact freshness;
- `build`: derived outputs only;
- `verify`: unit, integration, lint, and static checks;
- `package`: create a local candidate package;
- `publish`: separate human-only external write with exact target confirmation.

Do not combine package creation with publication. A local archive can be deterministic and low-risk;
uploading it to a registry or release is an external write and may have irreversible consequences.

## 8. Multi-repository or orchestrated system

Harness Reserve version 1 is project-scoped. For a system with several repositories, use a parent
project adapter that delegates to tracked orchestration scripts already responsible for those
repositories.

Do not let the shared runtime discover and run arbitrary neighboring repositories. The parent
adapter should declare:

- exact child repository identities;
- exact tracked orchestration entry points;
- expected versions or commits where needed;
- aggregate result rules;
- failure and rollback boundaries.

A child repository can also adopt Harness Reserve independently. Parent orchestration should call
stable child project commands rather than reaching into child internals.

## 9. Long-running workflow

The reference runtime is foreground and synchronous. A long-running action should either:

1. remain in the foreground with a realistic timeout and clear progress from the project script; or
2. delegate to an existing project-owned service and return a safe run identifier plus a separate
   `status` action.

Do not add a generic background daemon to the shared runtime merely to support one project. Do not
report work as complete when only a detached process was started.

## 10. Destructive or irreversible workflow

Examples include deleting data, migrating schemas, flashing hardware, deploying, publishing,
changing production configuration, and writing to external systems.

These actions are not good first adopters. When a project genuinely needs one:

- keep it human-only;
- use an explicit confirmation phrase that names the target;
- require project-specific preflight evidence;
- require clean Git or another relevant state gate;
- create rollback material where possible;
- record aggregate before/after hashes or identifiers;
- never let a handoff packet imply that confirmation has already been granted.

## 11. Anti-patterns

Reject an adapter that:

- accepts a free-form command, argument tail, path, environment map, or executable name;
- copies the project's pipeline into `.harness-reserve/actions/`;
- calls an LLM for `status`, `use`, or another deterministic operation;
- writes canonical files from a candidate-generation action;
- labels internet access as loopback or canonical writes as derived-only;
- records stdout, stderr, source text, prompts, or secrets in a generic receipt;
- deploys, publishes, commits, or pushes as part of an ordinary `verify` action;
- hides a paid API fallback behind a local command;
- treats capability metadata as an OS sandbox;
- returns PASS when the project script failed or when stale state remains undisclosed.

Aggregate receipts and handoffs are minimized local evidence, not automatically safe publication
artifacts. They retain local identity/path metadata and project-asserted safe fields.

## 12. Adapter review checklist

For every action, confirm:

- [ ] The action maps to one understandable user intention.
- [ ] The entry point is tracked and repository-relative.
- [ ] The adapter delegates rather than reimplements.
- [ ] Parameters are typed, bounded, and necessary.
- [ ] Authority labels match actual behavior.
- [ ] Confirmation is at least as strict as the runtime floor.
- [ ] The action has a finite timeout and honest failure mapping.
- [ ] The action-result summary is aggregate and safe.
- [ ] Model invocation is disabled unless the action is low-authority and deterministic.
- [ ] Candidate output cannot overwrite canonical state.
- [ ] The underlying project remains usable without Harness Reserve.
