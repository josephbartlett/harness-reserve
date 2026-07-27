# Project state and outcome semantics

## Outcome

Outcome applies to one action invocation.

- `PASS` - the declared action completed and its evidence is internally consistent.
- `DEGRADED` - the action completed its bounded work but an expected limitation remains.
- `BLOCK` - a known precondition, policy, or custody rule prevented the action.
- `ERROR` - an unexpected runtime, process, timeout, or malformed-result failure occurred.

## Project state

Project state is a broader aggregate classification.

- `READY` - ordinary intended local use is current and available.
- `DEGRADED` - useful operation is available with a known limitation.
- `BLOCKED` - a required condition prevents intended use.
- `STALE` - a derived view or semantic layer is known to lag current source.
- `UNCONFIGURED` - the adapter exists but has not been mapped to project behavior.
- `UNKNOWN` - the project has not supplied enough evidence to classify safely.

## Examples

A status action can return `PASS` plus `STALE`: the status check succeeded and proved that the current
view is stale.

A processing action can return `DEGRADED` plus `DEGRADED`: mechanical processing succeeded but human
or semantic review remains pending.

A use action can return `BLOCK` plus `STALE`: the project intentionally refused to open an outdated
view as current.

A verification action can return `ERROR` plus `UNKNOWN`: the test runner crashed before reliable
project state was established.

## Conservative fallback

When no action result is present, the runtime records project state `UNKNOWN`. A malformed action
result, process-start error, timeout, or observed manifest/entrypoint integrity drift forces
execution outcome `ERROR`. If the process exit is more severe than a project-supplied result, the
runtime suppresses that result's summary, state, evidence, and proposed next action.

These values describe technical execution and aggregate project condition. `PASS` and `READY` do
not imply human acceptance, candidate promotion, publication, deployment, or release authorization.
