# Foundation acceptance

Foundation technical acceptance requires reproducible evidence for every item below. The current
results and exact host versions belong in `VALIDATION.md`.

## Contract and path behavior

- project discovery works from the root and nested directories;
- duplicate JSON keys, non-finite numbers, malformed JSON, and unknown fields fail closed;
- action, project, parameter, authority, confirmation, intent, result, receipt, latest-pointer, and
  handoff shapes are closed;
- drive-qualified, UNC/rooted, traversal, alternate-stream/colon, reserved-device, trailing-dot/space,
  and escaping symlink/reparse paths are rejected where applicable;
- state stays at or below `.harness-reserve/state`, with handoffs below state;
- missing entrypoints/directories and unsupported runners block;
- Python actions run in explicit UTF-8 mode without writing bytecode into the adopter;
- the executable runner rejects script/document suffixes, requires `.exe`/`.com` on Windows, and
  validates ELF or Mach-O native magic on supported POSIX hosts immediately before launch.

## Dispatch and policy

- runner commands are argument arrays with `shell=False`; no arbitrary shell or trailing passthrough
  exists;
- parameters enforce required values, unique flags, boolean/string/integer/enum types, patterns,
  integer bounds, string limits, and sensitive redaction;
- every action declares all six authority dimensions;
- every sensitive authority combination receives the hard human-confirmation floor;
- model intent is dry-run by default and rejects project mismatch, human-only/high-authority actions,
  sensitive parameters, path-like text, and configured dirty-worktree use;
- confirmation cannot raise the model authority ceiling.

## Optional open-weight proposal

- `propose-intent` is fixed to one unauthenticated
  `127.0.0.1:11434/v1/chat/completions` request for `gpt-oss:20b`;
- it exposes no execute, confirmation, endpoint, model, credential, tool, retry, proxy, or paid
  fallback surface;
- the transmitted catalog contains only confirmation-free, low-authority, non-sensitive,
  `model_invocable` actions and omits paths, flags, fixed arguments, environment, authority, Git,
  receipt, and non-manifest repository content; transmitted descriptions and constraints are
  reviewed provider-visible manifest content;
- request, catalog, request-envelope, response-envelope, message-content, and total provider-call
  deadline bounds fail before unsafe continuation;
- refusal, malformed or oversized provider data, unknown fields, duplicate keys, non-finite values,
  tool/function calls, transport/HTTP failure, policy rejection, and storage failure return `BLOCK`
  without an intent;
- a valid selection passes the ordinary intent validator, writes one collision-safe file below
  `.harness-reserve/state/intents/` only after Git-ignore, containment, symlink/reparse, and
  post-provider destination revalidation, and returns `dry_run: true` plus `executed: false`;
- proposal writes no run receipt or latest pointer, and action execution remains a separate
  `dispatch-intent --execute` command;
- raw request, provider body, provider reasoning, and private failure text are absent from the saved
  intent and CLI JSON result.

These criteria are exercised with mocked HTTP transport; CI must not install Ollama or pull a model.
Live provider acceptance is a separate optional gate requiring suitable hardware and an explicit
privacy/performance review. Ollama is absent from the current validation host, whose discrete GPU
has 4 GB of VRAM. OpenAI's
[Ollama guidance](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama)
recommends at least 16 GB of VRAM or unified memory for `gpt-oss:20b`, so no live-model result is
claimed.

## Execution, evidence, and privacy

- timeouts and process-start errors produce aggregate ERROR receipts;
- nonzero exits cannot be converted to PASS by an action result;
- malformed results and manifest/entrypoint mutation or deletion fail conservatively;
- receipt/latest writes are atomic, and the latest pointer binds run id, exact path, and receipt
  digest;
- pointer/receipt identity and digest tampering is rejected;
- receipts record evidence counts and result presence/validity while omitting stdout, stderr, file
  contents, Git diffs, and sensitive parameter values;
- JSON mode suppresses action output and emits only the privacy-safe aggregate;
- a synthetic private marker is absent from receipt and handoff artifacts;
- handoff packets grant no authority and bind the latest validated receipt.

## Adapter and example

- initialization refuses overwrite and escaping symlink/reparse ancestors;
- generated state and candidate ignore guidance is present and doctor checks both;
- the template default/status returns `DEGRADED` plus `UNCONFIGURED`; all other stubs block and every
  generated action is human-only;
- the example proves list, validate, doctor, default/use, status, typed process, verify, latest,
  handoff, sensitive block/confirm, and eligible intent dry-run/execute;
- native Windows proves PowerShell argument/exit behavior, UTF-8 installation, missing-runtime
  failure, exact-marker CMD behavior, same-size external-path rejection, and the documented
  trusted-human batch boundary;
- the root `reserve.cmd` fails closed; management uses PowerShell.

## Optional protocol boundary

- the candidate schema binds provider, inputs, outputs, hashes, validation, and promotion state;
- candidate output paths remain below `outputs/`, and unvalidated promotion is schema-invalid;
- candidate generation/promotion and bounded maintenance remain project-owned protocols, not falsely
  claimed generic runtime capability.

## Authority boundary

A technical PASS is not Joey's review or acceptance. It is not real-project adoption, candidate
promotion, commit/push authority, package publication, deployment, or release approval. The public
MIT license and repository visibility do not weaken those separate human gates.
