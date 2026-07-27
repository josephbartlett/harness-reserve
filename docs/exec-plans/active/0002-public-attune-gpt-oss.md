# Execution plan 0002: public foundation, ATTUNE binding, and gpt-oss intent

Status: active
Owner: Joey Bartlett
Human gate: publication and initial release authorization remain explicit

## Goal

Prepare the first pristine public Harness Reserve revision with an MIT license, installable
source/wheel surfaces, a fixed-loopback open-weight intent proposer, and a thin provisional ATTUNE
maintenance binding that grants no product or release authority.

## Exact scope

- publish original Harness Reserve work under MIT, copyright Joey Bartlett;
- make `https://github.com/josephbartlett/harness-reserve` the canonical origin;
- preserve a dependency-free deterministic operator;
- add optional proposal-only `gpt-oss:20b` selection through local Ollama;
- adopt ATTUNE host-state `0.3.0` at exact commit
  `e55d1194a7da7899fcf601cccba2c941fe91876e`;
- keep ATTUNE runtime material and governance state ignored and removable;
- review and validate the complete first revision before public visibility.

## Gates

- [x] Code, schemas, docs, examples, tests, and package metadata agree.
- [x] The local-model proposer cannot execute, change endpoint/model, use credentials, retry, or
      fall back to a hosted API.
- [x] MIT licensing and any ATTUNE-derived Apache-2.0 notice are explicit.
- [x] The adapter template works from an installed wheel.
- [x] Line endings and executable bits are deterministic across Windows and Linux.
- [x] ATTUNE source and host are exact and clean before scaffold/bind.
- [x] Active `.attune/` content is absent from Git and scaffold inventory.
- [x] Focused contract, security, Windows, documentation, and acceptance reviews resolve or retain
      every material finding.
- [x] Native Windows, portable, package, JSON/schema, privacy, and fresh-clone checks pass.
- [ ] The exact initial commit is pushed privately and CI is green before visibility changes.
- [ ] Public visibility, repository protections, and security settings are verified separately.

## Deliberate boundaries

- ATTUNE is provisional and private; it is not a released or public product dependency.
- Harness Reserve remains clone-usable without ATTUNE.
- The ignored active ATTUNE binding is maintainer-local. A fresh clone currently has no supported
  ATTUNE rehydration command and governed bootstrap must fail closed there.
- Ollama and `gpt-oss:20b` are not installed or downloaded automatically.
- This machine is unsuitable for a credible live model claim; provider safety is mock-tested.
- No tag, GitHub Release, PyPI upload, deployment, or real-project adoption is in scope.

## Evidence log

`VALIDATION.md` records the source-bound evidence and limitations. The immutable commit SHA, its
ignored ATTUNE binding, hosted CI checks, and GitHub settings are necessarily post-commit evidence;
verify them against the same SHA before marking this plan complete.
