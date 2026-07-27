# Minimal Python project example

This small synthetic project proves the project-owned adapter contract. Its action scripts are
Python, while the Windows launch surface is exercised through PowerShell 7.

From the Harness Reserve repository root:

```powershell
.\reserve.ps1 --project-root .\examples\minimal-python-project list
.\reserve.ps1 --project-root .\examples\minimal-python-project validate
.\reserve.ps1 --project-root .\examples\minimal-python-project doctor
.\reserve.ps1 --project-root .\examples\minimal-python-project run
.\reserve.ps1 --project-root .\examples\minimal-python-project run status
.\reserve.ps1 --project-root .\examples\minimal-python-project run process --params-json '{"item":"sample","open-after":true}'
.\reserve.ps1 --project-root .\examples\minimal-python-project run verify
.\reserve.ps1 --project-root .\examples\minimal-python-project latest
.\reserve.ps1 --project-root .\examples\minimal-python-project handoff
```

`status.intent.json` selects only the read-only status action. The example deliberately permits that
one action in a dirty checkout so the uncommitted greenfield can dogfood both paths:

```powershell
.\reserve.ps1 --project-root .\examples\minimal-python-project dispatch-intent .\examples\minimal-python-project\status.intent.json
.\reserve.ps1 --project-root .\examples\minimal-python-project dispatch-intent .\examples\minimal-python-project\status.intent.json --execute
```

The tracked intent remains the deterministic, provider-free proof. If Ollama and `gpt-oss:20b` have
been installed and started separately, the optional fixed-loopback proposer can select from the same
eligible action surface:

```powershell
.\reserve.ps1 --project-root .\examples\minimal-python-project propose-intent `
    --request "Report readiness."
```

Only `status` is model-invocable in this example. A successful proposal writes a new intent below
`.harness-reserve/state/intents/`, prints its path and a dry-run plan, and creates neither a run
receipt nor `latest.json`. Inspect the printed file before using the separate dispatcher:

```powershell
.\reserve.ps1 --project-root .\examples\minimal-python-project dispatch-intent <printed-intent-path>
.\reserve.ps1 --project-root .\examples\minimal-python-project dispatch-intent <printed-intent-path> --execute
```

The proposer always calls `gpt-oss:20b` at
`127.0.0.1:11434/v1/chat/completions`; it has no execute, endpoint, model, credential, retry, or paid
fallback option. Do not put secrets or private text in `--request`: Harness Reserve omits the raw
request and provider response from its artifacts, but shell history and Ollama-managed logs are
outside that boundary.

This provider path is mock-tested only. Ollama is absent from the current validation host, whose
discrete GPU has 4 GB of VRAM; OpenAI's
[Ollama guide](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama)
recommends at least 16 GB of VRAM or unified memory for `gpt-oss:20b`.

The `serve-private` action does not start a server. It proves the hard confirmation floor:

```powershell
# Expected BLOCK 20
.\reserve.ps1 --project-root .\examples\minimal-python-project run serve-private --params-json '{"minutes":5}'

# Expected PASS after explicit human confirmation
.\reserve.ps1 --project-root .\examples\minimal-python-project run serve-private --params-json '{"minutes":5}' --confirm
```

The project CMD wrapper supports only the default and four exact tracked-marker actions
use/status/process/verify, with no trailing arguments:

```powershell
.\examples\minimal-python-project\harness.cmd
.\examples\minimal-python-project\harness.cmd status
.\examples\minimal-python-project\harness.cmd process
.\examples\minimal-python-project\harness.cmd verify
```

Use `harness.ps1` or `reserve.ps1` for typed parameters and any other action. Generated state and
candidate directories are ignored and must be removed before scaffold integrity validation.
