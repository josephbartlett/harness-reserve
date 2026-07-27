# ATTUNE compatibility and maintenance binding

Harness Reserve does not implement or replace the ATTUNE protocol, and its product runtime has no
ATTUNE dependency. Maintainers use a thin, removable host-state binding generated from the exact
provisional ATTUNE `codex-host-state/v1` adapter at:

```text
commit: e55d1194a7da7899fcf601cccba2c941fe91876e
tree:   8bfcb1125f69f957136207ec8755b499765a1bd4
implementation: 0.3.0
```

The tracked host configuration, declaration, and first-stage wrapper commit to the exact integration
and ATTUNE source bytes and authorize creation of one ignored active binding. That post-commit
binding binds the exact host commit, tree, and tracked integration bytes. The binding, object cache,
materialized ATTUNE closure, inputs, lock, and state stay ignored under `.attune/`. They are
maintenance evidence, not product state.

A practical mapping is:

| ATTUNE concern | Harness Reserve contribution |
|---|---|
| ANCHOR | project discovery, manifest, repository identity |
| TRACE | status action, run receipts, safe evidence |
| TARGET | one declared action and typed parameters |
| UNBLOCK | explicit BLOCK outcome and next action |
| NORMALIZE | project-owned adapter over existing scripts |
| ENCODE | action result, receipt, handoff packet |
| HARMONIZE | cross-project contract without domain coupling |
| BRIDGE | model-neutral continuation packet |
| MASTER GATE | bounded evidence from a confirmed action; ATTUNE/project remains authoritative |

The ATTUNE repository may reference Harness Reserve as an execution adapter. Harness Reserve should
not import ATTUNE internals or become authoritative over project orchestration. Reserve
confirmation is not an ATTUNE MASTER GATE and never grants lifecycle transition, promotion,
publication, or release authority.

## Current limitations

ATTUNE itself is provisional, private, unreleased, and public-readiness `BLOCK` at the pinned
revision. It is not presented as a public dependency.

An already-bound checkout verifies from its ignored Git-object cache and no longer depends on the
ordinary ATTUNE working tree. A fresh Harness Reserve clone does not currently have a supported
command to rehydrate those ignored binding surfaces. The governed wrapper therefore fails closed in
a fresh clone while the Harness Reserve operator remains fully usable. Do not normalize that
governance limitation as product failure or as ATTUNE success.

Repeated repository revisions require a new exact host binding or an explicit recovery decision;
the current create-only adapter must not be silently rewritten. Until ATTUNE supplies a reviewed
rehydration/rebinding path, pull requests and focused independent reviews are the durable public
maintenance mechanism, with ATTUNE state serving as maintainer-local bounded evidence.
