# Decision 0007: fixed-loopback open-weight intent proposal

## Status

Accepted for the initial public foundation.

## Decision

Provide one optional natural-language proposal command backed by local Ollama:

```text
propose-intent --request <text>
```

Fix the provider to `gpt-oss:20b` at
`127.0.0.1:11434/v1/chat/completions`. Do not expose an endpoint, model, credential, proxy, tool,
retry, execution, confirmation, or hosted fallback setting. Do not install Ollama or download a
model automatically.

The adapter sends the request and a reduced catalog containing only confirmation-free,
non-sensitive, low-authority `model_invocable` actions. It accepts one exact select-or-refuse JSON
object, supplies the public contract version, project id, and fixed reason itself, and applies the
existing deterministic intent policy. The system prompt requests low reasoning, supplies no tools,
and rejects provider tool or function calls.

A valid proposal is stored without overwrite below ignored
`.harness-reserve/state/intents/` and returned as an ordinary dry-run plan. It launches no action,
creates no run receipt, and does not update `latest.json`. Execution remains a separate human
command:

```text
dispatch-intent <intent-file> --execute
```

The dispatcher reloads current project state and reapplies all model-intent policy before execution.

## Reasons

- Deterministic operation remains available without a model.
- A fixed loopback and model make the first provider boundary small enough to inspect and test.
- The model selects only data already constrained by project-owned action metadata.
- Proposal and execution separation prevents natural language from becoming direct command
  authority.
- Existing operator-intent validation remains the single action-selection contract.
- Standard-library HTTP preserves the dependency-free runtime.
- No retry or fallback prevents hidden cost and accidental transmission to a remote provider.

## Privacy and failure boundary

Harness Reserve bounds the request, catalog, HTTP envelopes, response content, and timeout. It sends
no project files, executable paths, fixed arguments, environment values, authority metadata, Git
metadata, or receipts through the reference adapter. It supplies no model tools.

Raw requests, provider responses, reasoning, and provider error bodies are not written to intents,
receipts, or handoffs and are not echoed by the CLI. The selected action, non-sensitive parameters,
confidence, project identity, and fixed reason are stored in the ignored intent file.

The request can remain in shell history and is visible to the Ollama process. Ollama-managed logs,
model files, process isolation, and resource use are outside Harness Reserve's control. Provider
refusal, unavailability, malformed or oversized output, policy rejection, and safe-storage failure
all block without an intent or retry.

Intent publication also fails closed unless Git verifies the fixed destination as ignored. Existing
symlink/reparse components are rejected, and the path is revalidated after the provider wait and
before no-overwrite publication.

## Consequences

The fixed provider response is an internal adapter shape, not a new public JSON schema. Manifest,
operator-intent, receipt, and contract versions remain unchanged. Projects may continue to use
hand-authored or independently produced six-field intents without Ollama.

This decision intentionally does not create a generic provider framework, candidate generator,
coding agent, remote-model setting, or provider plugin surface. A future provider or protocol change
requires a separate decision with equivalent authority and privacy review.

Provider safety is currently mock-tested only. Ollama is absent from the validation host, whose
discrete NVIDIA GeForce RTX 3050 Ti Laptop GPU has 4 GB of VRAM. OpenAI's
[gpt-oss Ollama guidance](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama)
recommends at least 16 GB of VRAM or unified memory for `gpt-oss:20b` and notes that CPU offload is
slower. Live selection quality, latency, memory use, and provider-side privacy remain unverified.
