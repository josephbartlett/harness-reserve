# Adoption guide

## 1. Prepare Windows

Install Python 3.11 or later and PowerShell 7 (`pwsh`). If this checkout came from a downloaded
archive and Windows marked its files as internet-originated, review the checkout and remove that
mark only from the verified repository:

```powershell
Get-ChildItem -LiteralPath C:\Projects\harness-reserve -Recurse -File | Unblock-File
```

Do not weaken the machine execution policy or add `-ExecutionPolicy Bypass` to tracked launchers.

## 2. Choose a reference strategy

### Installed console command

Install the current checkout into a trusted Python environment:

```powershell
python -m pip install .
harness-reserve init `
    --target C:\Projects\my-project `
    --project-id my-project `
    --display-name "My Project"
```

Keep that environment's `harness-reserve` application on `PATH`. The generated `harness.ps1`
wrapper uses it only after the explicit checkout strategies below are absent. No package has been
published by this repository; installing from another source requires a separate provenance review.

### Environment-variable checkout

Clone Harness Reserve once and set:

```powershell
[Environment]::SetEnvironmentVariable(
    "HARNESS_RESERVE_HOME",
    "C:\Projects\harness-reserve",
    "User"
)
```

Open a new terminal afterward. This is the simplest strategy for one user and many projects.

### Project submodule

Place the shared repository at:

```text
.tools/harness-reserve/
```

This gives each project an explicit pinned version but adds submodule maintenance.

### Sibling checkout

Keep project repositories beside a checkout named `harness-reserve`. The generated launchers can
find it without additional configuration. This is convenient but less explicit than a pinned
submodule.

## 3. Generate the adapter

From the shared repository:

```powershell
.\reserve.ps1 init `
    --target C:\Projects\my-project `
    --project-id my-project `
    --display-name "My Project"
```

Initialization refuses to overwrite existing files or traverse a symlink/reparse ancestor. If an
error occurs, it removes only files and directories created by that initialization attempt.

## 4. Merge ignore rules

Copy the lines from:

```text
.harness-reserve/gitignore.append
```

into the project's root `.gitignore`. Confirm with:

```powershell
git check-ignore --no-index .harness-reserve/state/probe
git check-ignore --no-index .harness-reserve/candidates/probe
```

The synthetic child paths matter because Git does not report a directory-only rule for an absent
directory itself. `doctor` performs the same future-child check for both locations. Outside a Git
worktree it reports ignore state as unknown; an explicitly unignored location makes the doctor
result not OK. Do not continue with real private state until both checks print a matching ignore
rule and return exit 0.

## 5. Understand the Windows launchers

`harness.ps1` is the general project wrapper. It accepts action names and typed runtime options as a
PowerShell argument array.

`harness.cmd` is deliberately smaller: default, `use`, `status`, `process`, and `verify`, with no
additional arguments. It uses unique-size gating followed by exact tracked marker identity under
`.harness-reserve/cmd-actions/`. Same-size external files do not select an action; equivalent paths
to the actual marker may. Adding a manifest action does not add it to the CMD surface. Use
`harness.ps1` or `reserve.ps1` for typed parameters and other actions; extend the fixed CMD dispatch
only after explicit review.

The generated template returns `DEGRADED`/`UNCONFIGURED` with exit 10 for default/status. Its
use/process/verify stubs return BLOCK 20. Every generated action is human-only until an adopter
explicitly audits and enables `model_invocable`.

## 6. Audit existing project entry points

Before writing adapters, inventory what the project already has:

- ordinary app launcher;
- environment/bootstrap check;
- foreground input or synchronization pipeline;
- status or receipt generator;
- ordinary test command;
- human review package;
- local serve/share flow;
- current source-of-truth documents;
- private storage layout;
- publication and deployment gates.

The adapter should call these entry points rather than duplicate them.

## 7. Implement `status` first

Status should be aggregate and fast. It should answer questions such as:

- Is the app buildable or launchable?
- Are required local dependencies present?
- Is newly processed input ahead of semantic state?
- Is the current view stale?
- Is human review pending?
- Is a previous action blocked?

Status should not print private prose merely to prove readiness.

## 8. Implement `use`

`use` should represent the ordinary human experience:

- build and open a static local view;
- start a loopback development server;
- launch a desktop application;
- open a local dashboard;
- attach to an already-running process.

It should not modify canonical data merely to make the application open.

## 9. Implement `verify`

`verify` should run the normal non-destructive gate. It may create ephemeral caches or test outputs,
but must not refresh canonical private artifacts, deploy, publish, or rewrite source state unless the
project already defines those operations as non-destructive and safe.

## 10. Implement one processing action

Map the project's most valuable foreground workflow, such as:

- synchronize locally present recordings into a corpus;
- process new images into thumbnails;
- rebuild a search index;
- import synthetic messages;
- collect sensor data;
- regenerate a local report.

Be explicit about the difference between external synchronization and project processing. A project
script should not claim it synchronized Google Drive, a cloud bucket, or another external system
unless it actually did.

## 11. Classify authority honestly

Do not label a networked action `none` for convenience. Do not label canonical writes `derived-only`.
The labels are a review contract even where the OS does not enforce them.

## 12. Validate

```powershell
.\reserve.ps1 --project-root C:\Projects\my-project validate
.\reserve.ps1 --project-root C:\Projects\my-project doctor
C:\Projects\my-project\harness.cmd status
C:\Projects\my-project\harness.ps1 process --params-json '{"open-after":true}'
```

Then test:

- default action;
- unknown action;
- unknown parameter;
- missing dependency;
- blocked precondition;
- timeout;
- malformed action result;
- confirmation gate;
- dirty Git behavior where applicable;
- receipt privacy;
- continuation handoff.

## 13. Add optional local-model intent

Only after deterministic actions pass:

1. leave every action human-only until its implementation and authority are audited;
2. mark only eligible low-authority actions `model_invocable`;
3. keep any action requiring confirmation or declaring a sensitive parameter outside the reference
   proposal catalog;
4. manually install Ollama and pull `gpt-oss:20b` only on suitable local hardware;
5. run `propose-intent` and inspect its saved intent and dry-run plan;
6. dispatch that intent separately without `--execute`;
7. execute only after both dry runs remain correct and current.

Do not let the model produce a command line.

The reference proposer is fixed to one unauthenticated loopback call at
`127.0.0.1:11434/v1/chat/completions` with model `gpt-oss:20b`. It cannot change provider settings,
use credentials or tools, retry, execute, confirm, or fall back to a remote or paid API. Harness
Reserve does not install or pull the provider.

OpenAI's
[Ollama setup guide](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama)
recommends at least 16 GB of VRAM or unified memory for `gpt-oss:20b`; CPU offload can be slower.
Ollama is absent from the current validation host and its discrete GPU has 4 GB of VRAM, so the
provider path is mock-tested rather than live-validated.

With a separately prepared provider:

```powershell
.\reserve.ps1 --project-root C:\Projects\my-project propose-intent `
    --request "Report aggregate readiness."

.\reserve.ps1 --project-root C:\Projects\my-project `
    dispatch-intent <printed-intent-path>

.\reserve.ps1 --project-root C:\Projects\my-project `
    dispatch-intent <printed-intent-path> --execute
```

The proposer sends only the request and reduced eligible-action catalog, writes the validated
six-field intent below ignored `.harness-reserve/state/intents/`, and creates no action receipt.
The provider never receives entrypoint paths, fixed arguments, environment, Git metadata, receipts,
or non-manifest repository files through this adapter. The eligible descriptions and parameter
constraints are trusted manifest content sent to the provider, so review them for local-provider
disclosure before enabling model invocation.

Do not place secrets or private content in `--request`. Harness Reserve does not retain or echo the
raw request, response, or provider reasoning, but the request may remain in terminal history and
Ollama may maintain logs outside the runtime's privacy boundary.

## 14. Add candidate-only reasoning if needed

Create a project-specific candidate contract and validators. Keep the first implementation narrow.
For example, a transcription project may propose a candidate semantic refresh; a report project may
propose a candidate narrative. Do not implement generic promotion until project-specific custody and
staleness rules are clear.

The shared repository provides a candidate schema and protocol only. Candidate generation,
deterministic binding checks, semantic review, and promotion remain project-owned.

## 15. Project acceptance checklist

- [ ] `.harness-reserve/operator.json` validates.
- [ ] State and candidate directories are ignored.
- [ ] The fixed CMD marker files are tracked and the CMD surface has no typed or trailing input.
- [ ] Every action delegates to an existing or intentionally new tracked entry point.
- [ ] No adapter uses arbitrary command evaluation.
- [ ] `status` is aggregate-only.
- [ ] `use` opens the ordinary experience without semantic fabrication.
- [ ] `process` distinguishes mechanical completion from interpretive completion.
- [ ] `verify` is non-destructive.
- [ ] Sensitive actions require confirmation.
- [ ] Model-invocable actions stay below the local-model authority ceiling.
- [ ] Any enabled reference proposal action is confirmation-free and has no sensitive parameter.
- [ ] Git verifies proposal intent storage as ignored, its path has no symlink/reparse component,
      and a proposal never creates a receipt or executes an action.
- [ ] Provider installation, hardware suitability, logs, and resource limits are reviewed
      separately from Harness Reserve's mocked provider tests.
- [ ] Receipts contain no private content or secrets.
- [ ] Handoff accurately states remaining limitations.
- [ ] Receipt and handoff paths/metadata are treated as local artifacts, not publication-ready data.
- [ ] Removing Harness Reserve does not destroy the underlying project capability.
