# Contributing

Harness Reserve is intentionally small. Contributions should preserve the closed operator contract,
project-owned domain behavior, standard-library runtime, Windows-first usability, and honest
authority boundaries.

## Before changing code

Read `AGENTS.md`, then follow its progressive-disclosure order. Open an issue before proposing a
new dependency, runner, authority value, provider, or breaking contract change.

Never include credentials, private project content, transcripts, command output, Git diffs, or
machine-local state in an issue, pull request, fixture, receipt, or handoff.

## Development

Create a branch from `main`, make one focused change, and update contracts, schemas, documentation,
examples, and tests together whenever behavior changes.

On Windows:

```powershell
python -m pip install -e ".[validation]"
.\scripts\test.ps1
```

On a POSIX host:

```bash
python -m pip install -e ".[validation]"
bash ./scripts/test.sh
```

Before requesting review, also run:

```powershell
python -B scripts\validate_scaffold.py
git diff --check
```

Native Windows behavior must be exercised for launcher, PowerShell, CMD, path, or process changes.
Do not infer Windows acceptance from a portable-only test.

## Review and authority

All post-bootstrap changes use pull requests and the focused review appropriate to the claim and
risk. A green test run or reviewer `PASS` is technical evidence only. It does not authorize merge,
release, publication, deployment, real-project adoption, or semantic promotion.

Maintainers may use the repository's provisional, ignored ATTUNE host binding to preserve exact
subject and review state. That local governance state is optional for contributors, grants no
authority, and is not part of the product runtime.

By contributing, you agree that your contribution is licensed under the repository's MIT license
unless a file explicitly identifies a compatible third-party license.
