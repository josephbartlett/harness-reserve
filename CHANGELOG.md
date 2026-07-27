# Changelog

## 0.1.0 - Initial public foundation

- Added dependency-free reference runtime.
- Added strict manifest, action result, receipt, intent, handoff, and candidate contracts.
- Added Windows launchers and fail-closed PowerShell project adapter template.
- Added aggregate receipts, safe handoffs, and local-model intent dry-run.
- Added a proposal-only open-weight path fixed to local Ollama `gpt-oss:20b` at
  `127.0.0.1:11434`, with a minimized action catalog, bounded request/response handling, strict
  select-or-refuse adaptation, ignored no-overwrite intent storage, and separate explicit dispatch.
- Added mocked provider failure/privacy coverage with no automatic model download, retry, remote
  endpoint, credentials, execution, or paid fallback. Live inference remains unverified because
  Ollama is absent from the validation host and its discrete GPU has 4 GB of VRAM versus the
  recommended 16 GB or more.
- Added executable example, tests, CI, adoption patterns, validation status, and a SHA-256 scaffold inventory.
- Hardened strict JSON, portable Windows path containment, explicit authority, local-model ceilings,
  conservative result reconciliation, Git inspection, atomic digest-bound receipts, and handoff
  integrity.
- Added fail-closed Windows batch boundaries, safe PowerShell argument bridging, generated-adapter
  overwrite/reparse protection, and native Windows regression coverage.
- Aligned all seven closed JSON schemas, executable documentation, and the candidate-only protocol.
- Added the MIT License with public repository, security, and contribution guidance.

Native technical validation is recorded in `VALIDATION.md`. This changelog does not imply human
acceptance, package release authorization, deployment, or real-project adoption.
