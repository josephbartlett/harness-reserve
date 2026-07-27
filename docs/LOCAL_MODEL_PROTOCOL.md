# Local-model protocol

Harness Reserve permits two optional, separate roles for a local model:

1. propose one deterministic, allowlisted operator action;
2. generate project-owned candidate work under ignored storage.

The deterministic operator does not require a model. The implemented reference provider can only
propose an operator intent and dry-run it. It does not execute actions, generate candidates,
validate semantic quality, promote candidate work, or fall back to a hosted service.

## Reference open-weight proposer

The reference provider path is deliberately fixed:

```text
Ollama: 127.0.0.1:11434
API path: /v1/chat/completions
Model: gpt-oss:20b
```

Harness Reserve supplies no endpoint, port, model, credential, proxy, tool, retry, or provider
fallback option. It never installs Ollama, pulls a model, or contacts a paid API. The provider call
uses Python's standard-library HTTP client and makes one attempt.

OpenAI's
[gpt-oss Ollama guide](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama)
documents manual setup, including:

```powershell
ollama pull gpt-oss:20b
ollama run gpt-oss:20b
```

That guide says `gpt-oss:20b` works best with at least 16 GB of VRAM or unified memory and that CPU
offload is possible but slower. Harness Reserve does not use the Responses API or introduce a proxy;
it uses Ollama's local Chat Completions-compatible path directly.

Ollama is absent from the current validation host. Its discrete NVIDIA GeForce RTX 3050 Ti Laptop
GPU has 4 GB of VRAM, below the official 16 GB guidance. The implementation is therefore supported
by mocked transport, policy, storage, and privacy tests only. Live inference quality, latency,
resource behavior, and provider-side privacy have not been validated on that machine.

## Proposal flow

After the project manifest and deterministic actions pass `validate` and `doctor`, a human may ask
for a proposal:

```powershell
.\reserve.ps1 --project-root C:\Projects\example propose-intent `
    --request "Report aggregate readiness."
```

The proposer:

1. validates the request and provider timeout;
2. requires Git to verify the reserved intent location as ignored;
3. builds a reduced eligible-action catalog;
4. makes one fixed-loopback provider request;
5. accepts one exact select-or-refuse JSON object;
6. converts a selection into the existing six-field operator intent;
7. applies the deterministic intent and action policy;
8. obtains the ordinary redacted dry-run plan;
9. atomically creates a new intent below `.harness-reserve/state/intents/`.

It launches no action, writes no run receipt, and does not update `latest.json`. The command accepts
no `--execute`, `--confirm`, `--confirmation-text`, `--model`, or `--endpoint` option.

Inspect the printed intent path. Dispatch remains a separate human action:

```powershell
.\reserve.ps1 --project-root C:\Projects\example dispatch-intent <printed-intent-path>
.\reserve.ps1 --project-root C:\Projects\example dispatch-intent <printed-intent-path> --execute
```

The first dispatch is another dry run. The second explicitly authorizes execution of the selected
action only after the dispatcher reloads the current manifest and reapplies project identity,
parameter, Git-state, authority, and confirmation policy.

## Eligible catalog

The proposer catalog contains only actions that:

- declare `model_invocable: true`;
- remain inside the model authority ceiling;
- declare no sensitive parameter;
- require neither manifest confirmation nor hard-floor confirmation;
- have model-safe declared defaults;
- are not blocked by a known nonzero dirty count when
  `constraints.forbid_model_actions_when_dirty` is true.

For each eligible action, the provider receives its id and description plus reduced parameter
metadata: type, required state, description, integer bounds, safe enum values, and string pattern
where present. The provider does not receive project identity, runner, entrypoint, working
directory, fixed arguments, parameter flags or defaults, environment, authority metadata, hidden
actions, Git metadata, receipts, or non-manifest repository files.

Action and parameter descriptions, safe enum values, and regex patterns in that reduced catalog are
trusted manifest content. Harness Reserve does not semantically scrub them for private prose or
path-like text; adopters must review those fields before enabling model invocation.

Every provider-selected string or enum parameter still must match the portable token rule
`^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$`. Paths, whitespace, dots, command punctuation, and longer
values fail during deterministic intent validation.

## Provider response and public intent

The internal provider content must be exactly one of:

```json
{"decision":"select","action":"status","parameters":{},"confidence":0.98}
```

```json
{"decision":"refuse"}
```

Unknown or missing fields, duplicate keys, non-finite numbers, prose, malformed JSON, unknown
actions, tool or function calls, invalid parameters, and out-of-range confidence fail closed. A
refusal returns `BLOCK` and writes no intent. The internal selector is adapter data, not a new public
schema.

For a selection, Harness Reserve supplies the contract version, current project id, and a fixed
aggregate reason. The stored public intent retains the existing closed shape:

```json
{
  "contract_version": 1,
  "project_id": "example-project",
  "action": "status",
  "parameters": {},
  "reason": "Selected by the fixed local gpt-oss proposal adapter after deterministic validation.",
  "confidence": 0.98
}
```

Existing files are never overwritten. The collision-safe filename is:

```text
.harness-reserve/state/intents/<UTC timestamp>-<random>.intent.json
```

This fixed location stays below the reserved state root even when the manifest chooses a deeper
runtime state directory. Git must verify it as ignored, existing symlink/reparse path components are
rejected, and the destination is re-resolved after the provider wait and before no-overwrite
publication.

## Bounds and failure behavior

| Item | Bound |
|---|---:|
| user request | non-empty UTF-8, no null, at most 2000 characters |
| eligible catalog | at most 32 KiB |
| HTTP request envelope | at most 64 KiB |
| HTTP response envelope | at most 64 KiB |
| provider message content | at most 16 KiB |
| total provider-call deadline | integer from 5 through 900 seconds; default 300 |
| attempts | one |

The system prompt starts with `Reasoning: low`. The request uses `stream: false`, JSON-object
response format, temperature zero, and no tools; provider tool or function calls are rejected.
Connection errors, timeouts, non-success HTTP responses, oversized or malformed data, provider
refusal, deterministic policy rejection, and safe-storage failure all return `BLOCK`. Error output
does not include the raw provider body or underlying private exception text. There is no retry and
no remote or paid fallback.

OpenAI's
[Harmony reasoning guidance](https://developers.openai.com/cookbook/articles/openai-harmony#reasoning)
warns that raw chain-of-thought should not be shown to end users. Harness Reserve treats provider
reasoning as untrusted private output and never includes it in the saved intent or dry-run result.

## Privacy boundary

Harness Reserve does not write or echo:

- the raw `--request` text;
- the raw provider response;
- provider reasoning or analysis;
- provider error bodies.

It does persist the selected action, non-sensitive parameters, confidence, current project id,
contract version, and fixed aggregate reason in the ignored intent file. The dry-run plan also shows
the selected action, redacted parameters, entrypoint, working directory, and declared authority so
the human can review what would run.

The request text is still transmitted to the local Ollama process. It may remain in PowerShell or
terminal history, and Ollama may keep its own logs outside Harness Reserve. The ignored state
directory is not a confidentiality boundary. Do not include secrets, credentials, private source
text, transcript prose, file contents, or other sensitive material in `--request`.

## Hand-authored intent

Ollama is optional. A trusted local tool or human may create the same six-field
`operator-intent.schema.json` document and use `dispatch-intent` directly. The same project-id,
model-invocable, authority, parameter, sensitive-field, token, dirty-worktree, and dry-run rules
apply.

Confirmation never raises the model ceiling. Private-LAN/internet, Git/external writes, secret
access, unrestricted project writes, and canonical semantic authority remain ineligible for model
intent.

## Candidate protocol

Candidate work is project-specific. The shared repository provides
`schemas/candidate-manifest.schema.json` and design rules, not a generic generator or promoter.

Minimum layout:

```text
.harness-reserve/candidates/<kind>/<candidate-id>/
  candidate-manifest.json
  outputs/
  validation/
  review/
```

The candidate manifest binds:

- project, candidate, and kind ids;
- creation time and provider/model identity;
- repository-relative input paths and lowercase SHA-256 digests;
- output paths and lowercase SHA-256 digests;
- deterministic validation checks;
- promotion state.

Output paths in the manifest are relative to the candidate directory and must start with `outputs/`.
The schema permits `VALIDATED` or `PROMOTED` only when validation state is `PASS`, but schema
validity is not semantic approval and grants no promotion authority.

Project-owned candidate generation must keep canonical project bytes unchanged, recheck source
bindings, and write only below the candidate root. A separate human-invoked promotion action must
revalidate current inputs, apply project custody rules, create rollback evidence, and require the
hard confirmation floor for canonical semantic authority. A model cannot select or confirm
promotion of its own output.

The reference gpt-oss proposer does not generate candidate content. Any future candidate provider
must remain project-owned, independently constrained, and free of hidden paid fallback.
