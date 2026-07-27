# Decision 0006: provisional ATTUNE maintenance binding

## Status

Accepted for the initial public foundation.

## Decision

Use the generated `codex-host-state/v1` adapter from exact ATTUNE commit
`e55d1194a7da7899fcf601cccba2c941fe91876e`, tree
`8bfcb1125f69f957136207ec8755b499765a1bd4`, implementation `0.3.0`, only as
optional maintainer-local governance.

Keep the Harness Reserve runtime independent. Track only the generated configuration, declaration,
and first-stage wrapper. Ignore the active binding, object cache, materialized closure, inputs,
lock, and state. Exclude `.attune/` from product validation and integrity inventory.

## Reasons

- Exact byte and host identity binding improves custody of review claims.
- The adapter is thin and removable rather than a second product runtime.
- ATTUNE evidence preserves review state without gaining human authority.
- Product users and contributors must not need access to a private governance repository.

## Consequences

The ordinary operator is fully clone-recoverable without ATTUNE. The pinned ATTUNE candidate is
private, provisional, unreleased, and not a public dependency.

A fresh clone cannot currently rehydrate the ignored active binding and must fail governed ATTUNE
bootstrap closed. The adapter is also create-only, so a later host revision needs an explicit
recovery/rebinding decision. Public pull-request and CI controls remain the durable maintenance
mechanism until a reviewed ATTUNE evolution closes those gaps.

The generated wrapper originated in an Apache-2.0 ATTUNE lineage authored by Joey Bartlett. The
copyright holder's instruction selects the repository MIT license for this tracked generated copy;
the exact origin remains documented here rather than being erased.
