## What changed

Describe the smallest behavior or documentation change.

## Claim and risk

- Claim being reviewed:
- Exact source/subject revision:
- Authority or privacy boundary affected:
- Risk level and focused reviewer lane:

## Validation

- [ ] `.\scripts\test.ps1` on native Windows, or the exact untested Windows gap is stated
- [ ] `bash ./scripts/test.sh` on a portable host when relevant
- [ ] Python compiles, tracked JSON parses, and schemas/fixtures validate
- [ ] Documentation, contracts, examples, and tests agree
- [ ] No generated state, candidate content, secrets, private data, or command output is included
- [ ] `SCAFFOLD_MANIFEST.json` was regenerated after the final source change
- [ ] `git diff --check` passes

## Review outcome

- Technical result:
- Unresolved findings or disagreement:
- Human merge/release decision: **not inferred from technical PASS**
