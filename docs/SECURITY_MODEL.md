# Security model

Harness Reserve reduces accidental and model-mediated overreach in trusted local repositories. It is
a closed dispatcher and evidence format, not an operating-system sandbox.

## 1. Trust boundary

The shared runtime, selected Python or PowerShell interpreter, project manifest, and tracked project
entrypoints are in the trusted computing base. Authority labels describe and gate expected behavior;
they do not stop a dishonest or compromised action from using filesystem, network, device, or
process authority already available to its account.

Harness Reserve does not defend against:

- a malicious or incorrectly classified tracked action;
- a compromised interpreter, native executable, dependency, or operating system;
- an administrator-level process;
- secrets already present in the inherited environment;
- local process inspection of child arguments;
- a project action that prints or exfiltrates sensitive data;
- reparse-point or file replacement races after validation;
- forged local state by an actor able to rewrite both evidence and its bindings;
- resource exhaustion from unbounded action output or an adversarial child process.

The runtime does not claim ACL, firewall, container, virtual-machine, credential, or language-sandbox
isolation.

## 2. Threats addressed

The reference implementation mechanically addresses:

- undeclared actions and parameters;
- command strings, shell runners, trailing passthrough, and model-selected paths;
- unsupported runners and script smuggling through the executable runner;
- malformed, duplicate-key, non-finite, or unknown-field JSON;
- portable path escape, Windows drive/UNC/device syntax, NTFS alternate streams, and observed
  symlink/reparse escape;
- manifest attempts to weaken sensitive confirmation floors;
- model actions above a stricter authority and parameter ceiling;
- provider proposal of hidden, confirmation-gated, sensitive-parameter, or otherwise ineligible
  actions;
- configurable or non-loopback model endpoints, provider credentials, retries, and hosted fallback;
- receipt storage of stdout, stderr, file contents, Git diffs, and sensitive parameter values;
- a less-conservative action result overriding process failure;
- observed manifest or entrypoint mutation during execution;
- latest-pointer path, digest, run-id, and project-identity mismatch;
- continuation packets being mistaken for delegated authority.

## 3. Closed process construction

The manifest may declare only a fixed runner, repository-relative entrypoint, fixed literal argument
array, fixed literal environment entries, and typed flag mappings. Runtime process construction uses
an argument array with `shell=False`.

Forbidden designs include:

- command-string fields or arbitrary positional tails;
- Python `shell=True`, `os.system`, or PowerShell `Invoke-Expression`;
- model-selected executable names, working directories, environment maps, or paths;
- environment expansion inside entrypoint paths;
- batch, script, shortcut, or document files hidden behind `runner: executable`.

Python actions use the current interpreter with `-X utf8 -B`, making text encoding explicit and
suppressing bytecode in the adopting project. PowerShell actions use PowerShell 7 with
`-NoLogo -NoProfile -NonInteractive -File`. Native executable actions are repository-relative;
Windows requires `.exe` or `.com`, Linux/other supported non-macOS POSIX hosts require ELF magic,
and macOS requires Mach-O or fat Mach-O magic. The native format is rechecked immediately before
launch.

## 4. Windows launcher boundary

Windows batch parsing occurs before a `.cmd` file can validate its arguments. Harness Reserve
therefore does not use batch as a general argument transport:

- repository-level `reserve.cmd` always returns `BLOCK`;
- project `harness.cmd` recognizes only the default and fixed `use`, `status`, `process`, and
  `verify` actions through exact tracked marker identity after a size gate;
- it rejects extra arguments and never forwards caller text into a command;
- typed parameters and all other actions go through `harness.ps1` or `reserve.ps1`.

The fixed project wrapper is a trusted-human convenience, not a boundary for untrusted input. Do not
construct a `.cmd` invocation from model output, filenames, network data, or other uncontrolled
text—even if the intended action is allowlisted.

`reserve.ps1` transports its received argument array to the Python bridge as JSON on standard input,
avoiding dependence on PowerShell native argument-passing modes. Python isolated mode ignores the
caller directory and environment import path; the launcher inserts only this checkout's inspected
`src` directory, and explicit UTF-8 mode preserves Unicode paths and labels across the native pipe.
The launcher then restores the caller's `PYTHONPATH`. Neither runtime nor project launchers use an
execution-policy bypass.

## 5. Path containment

Entrypoints, working directories, state, handoffs, receipt pointers, and evidence paths are validated
as portable repository-relative text and then canonically resolved inside the project root. State is
further confined to `.harness-reserve/state`, and handoffs are confined below state.

The path layer rejects Windows drives, drive-relative paths, rooted and UNC forms, device forms,
colons/alternate streams, parent traversal, reserved device basenames, nulls, and components ending
in a dot or space.

Existing symlink and reparse targets are included in canonical resolution. Adapter initialization
also refuses symlink or reparse-point ancestors and uses exclusive file creation. These checks do not
eliminate time-of-check/time-of-use races or provide a filesystem sandbox. Projects with adversarial
local writers require OS-level containment.

## 6. Confirmation and authority

The hard confirmation floor covers private-LAN and internet access, Git write and publish,
external-system writes, secret access, canonical semantic authority, and unrestricted project
writes. A manifest cannot turn that floor off.

Confirmation is deterministic user input, not delegated standing permission. It approves only the
selected invocation and does not authorize later commit, push, release, publication, deployment, or
candidate promotion.

Authority labels remain claims about trusted scripts. A script declared `network: none` can still
use the network unless the script or operating system prevents it.

## 7. Git inspection

Git inspection records aggregate repository availability, exact repository-root identity, branch,
commit, and dirty path count. It never captures a diff.

The runtime strips a bounded set of Git control environment variables, disables system
configuration and optional locks, and overrides fsmonitor and untracked-cache helpers for its reads.
Direct human confirmation is evaluated before these Git commands. A project nested inside a
different repository is reported explicitly and receives no dirty count; actions requiring
known-clean Git block when the count is unavailable.

Repository-local state is still trusted. Harness Reserve does not authenticate Git, repository
configuration, commits, or worktree contents.

## 8. Environment, arguments, and secrets

Actions inherit the current process environment because ordinary project tools commonly require
`PATH` and other local configuration. Fixed manifest entries and runtime-owned
`HARNESS_RESERVE_*` values are added.

Sensitive parameter redaction protects receipts, dry-run plans, and command previews only. The child
receives the real value, and it may be visible to local process inspection or action output.
Projects with secret-sensitive actions should:

- declare `secrets: read` and remain human-only;
- use a project-owned protected input mechanism instead of command-line secrets where possible;
- construct a minimal environment in the trusted adapter;
- avoid printing secrets or marking secret-derived evidence safe;
- use OS-level credential and process controls appropriate to the project.

Contract version 1 does not provide environment isolation or a generic secret transport.

## 9. Output, receipts, and handoffs

The core captures complete stdout and stderr in memory while an action runs. In ordinary mode it
displays them to the local caller. In `--json` mode it suppresses them so stdout is one
machine-readable JSON document. It never writes them into the generic receipt or handoff.

Capture is not size-bounded in contract version 1. A noisy or malicious action can consume memory,
and sensitive output exists transiently in the runtime process. Projects should keep action output
bounded and aggregate.

Receipts contain redacted parameters, local project and Git metadata, hashes, counts, and fields the
project explicitly calls safe. They contain no stdout, stderr, file contents, or Git diff. A
project's `safe_summary`, warnings, evidence labels, and `safe_to_share` flag are assertions by
trusted project code, not semantic inspection by the runtime.

The latest pointer binds one expected receipt path to a SHA-256 and validation checks exact shape,
run id, project id/root, and digest. Pre/post manifest and entrypoint hashes detect observed drift.
Neither mechanism is signed or tamper-proof: an actor able to rewrite all local state can forge new
consistent artifacts.

A handoff is built only from a validated latest receipt and current aggregate Git state. Its static
boundary says that it grants no authority. The project-supplied safe summary and recommended next
step are quoted in Markdown but remain untrusted data. Receipts and handoffs may contain absolute
local repository paths, branch names, commit ids, and other sensitive metadata; review before
sharing.

## 10. Timeouts and process lifetime

Actions run synchronously with a finite declared timeout. On timeout the outcome is `ERROR`. The
runtime attempts process-tree termination with `taskkill /T /F` on Windows and a process group on
portable systems. Its final output drain is also bounded; if inherited pipe handles remain open, it
closes its local pipe handles and records a warning rather than waiting without limit.

This is best effort, not a Windows Job Object or durable lifecycle manager. Descendants may escape,
ignore termination, or outlive the parent. Long-running services must remain project-owned and
expose separate deterministic status.

## 11. Model intent

Model intent is data, not a command. Dispatch is dry-run by default and requires:

- matching project identity;
- one declared, explicitly `model_invocable` action;
- valid typed parameters;
- low authority across every dimension;
- no declared sensitive parameter;
- portable token-only string and enum values;
- no known nonzero dirty count when the manifest enables the model-dirty gate.

Model intent cannot request private-LAN/internet access, unrestricted or ordinary workspace writes,
Git writes, external writes, secret access, or canonical semantic authority. Human `--confirm`
cannot raise this ceiling.

The optional reference proposer is a separate, narrower trust boundary. It sends one unauthenticated
HTTP request to literal loopback `127.0.0.1:11434/v1/chat/completions` for fixed model
`gpt-oss:20b`. It exposes no endpoint, model, credential, tool, retry, or fallback setting. It
cannot execute, confirm, or dispatch the selected action.

Before contacting Ollama, the proposer removes actions that require confirmation or fail the
existing model-invocation policy. The provider receives only the human request and a reduced catalog
of eligible action ids, descriptions, and typed parameter constraints. It does not receive
entrypoint or working-directory paths, fixed arguments, flags, environment values, authority
metadata, project identity, Git metadata, receipts, or non-manifest repository files through this
path. The
adapter supplies no tools to the model. Descriptions, enum values, and patterns in the reduced
catalog are trusted manifest content and are not semantic privacy filters; adopters must review
them before enabling model invocation.

Provider output remains untrusted. Only one select-or-refuse JSON object is accepted from the single
message content; tool or function calls are rejected even if content is also present. The selected
action and parameters then pass through the ordinary closed intent validator and dry-run policy. A
refusal, malformed response, unavailable provider, HTTP failure, policy violation, or storage
failure returns `BLOCK`, writes no intent, and is not retried. There is no paid or remote fallback.

The adapter bounds the user request to 2000 characters, the catalog to 32 KiB, each HTTP envelope to
64 KiB, response content to 16 KiB, and total provider-call deadline to 5–900 seconds. The system
message requests low reasoning. Bounds reduce accidental resource use but do not make the local
model service an OS sandbox or prevent resource use inside Ollama.

Harness Reserve does not store or echo the raw request, raw provider response, or model reasoning.
It persists only the validated public intent: action, non-sensitive parameters, confidence,
runtime-supplied project/version fields, and a fixed aggregate reason. The human request is still
visible to the local Ollama process, may remain in PowerShell history, and may be retained in
provider-managed logs. Those logs and Ollama's process, model files, resource use, and local
configuration are outside Harness Reserve's privacy and integrity boundary. Do not include secrets
or private source content in `--request`.

The fixed intent destination must be verifiably ignored by Git. Existing symlink/reparse components
are rejected, and the path is revalidated after the provider wait and before no-overwrite
publication. These checks reduce accidental redirection but do not eliminate filesystem races or
turn ignored state into confidential storage.

Provider safety is currently supported by mocked HTTP and privacy tests only. Ollama is absent on
the validation host, whose discrete NVIDIA GPU has 4 GB of VRAM. OpenAI's
[Ollama guidance](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama)
recommends at least 16 GB of VRAM or unified memory for `gpt-oss:20b`; CPU offload may be slower.
Harness Reserve therefore makes no live inference, performance, or provider-side privacy claim for
that host.

## 12. Candidate and maintenance limits

Candidate support is a schema and protocol, not an enforcement service. The schema can require
relative bindings and `outputs/` paths in a manifest, but it cannot stop an arbitrary provider
process from writing elsewhere. A project-owned generator must be constrained independently and
must prove canonical files stayed byte-identical.

Generation and promotion must be separate. A model cannot choose or confirm its own promotion.
Deterministic source-binding validation, human review, rollback material, and canonical writes are
project-owned future adoption work.

The maintenance plane is unimplemented. Any future local coding lane requires a disposable
worktree, bounded task packet, strict diff checks, and no commit, push, merge, deployment, or
publication authority.

## 13. Adoption checklist for sensitive projects

- inspect every tracked entrypoint and its real authority;
- confirm state and candidate paths are ignored;
- run `validate` and `doctor`;
- exercise unknown actions, parameters, path forms, and confirmation gates;
- test timeout and process-start failures with synthetic fixtures;
- inspect receipts, latest pointers, and handoffs for unexpected private content;
- keep secret, external-write, publication, and deployment actions human-only;
- document the OS-level controls beyond Harness Reserve;
- preserve separate human review, lifecycle, and release gates.

Technical validation establishes only the tested operator behavior. It does not establish human
acceptance, regulatory fitness, semantic correctness, release readiness, or permission to publish.
