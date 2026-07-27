# Maintaining Harness Reserve

## Ordinary change flow

After the initial bootstrap, every change starts on a branch and enters `main` through a pull
request. Bind the claim to the exact revision and affected contract surface, run the smallest
relevant deterministic checks, and add independent review only for the material uncertainty.

The pull request must keep these outcomes separate:

1. deterministic technical result;
2. focused reviewer result and unresolved disagreement;
3. human merge decision;
4. any later release or publication decision.

No result promotes itself.

## Risk and review routing

Use a proportional route:

| Risk | Default review |
|---|---|
| Documentation-only, no contract claim | author checks plus consistency review |
| Local implementation or test correction | deterministic suite plus one focused reviewer |
| Contract, authority, privacy, path, runner, or receipt change | contract/security review plus native platform evidence |
| Model-provider or candidate boundary | provider/privacy review plus adversarial fixtures |
| Publication, release, destructive action, or real-project adoption | exact human gate after technical review |

Role labels alone do not prove independence. Preserve a `BLOCK`, timeout, or material disagreement
until the exact finding is resolved or explicitly accepted by the human gate.

## ATTUNE maintainer binding

The optional tracked ATTUNE surfaces are:

```text
attune/attune-host-config.json
attune/attune-host-declaration.json
tools/attune_host.py
```

The exact source pin and limitation are recorded in `docs/ATTUNE_COMPATIBILITY.md`. Verify an active
binding without changing product state:

```powershell
python -I -S -B .\tools\attune_host.py
```

The active binding and all ATTUNE state are ignored under `.attune/`; none belongs in a commit,
scaffold inventory, issue, receipt, or public review attachment. Harness Reserve validation
deliberately excludes that directory.

The current ATTUNE adopter is create-only. It does not provide a supported fresh-clone hydrate or
routine rebind command. Do not hand-edit generated declarations, copy active binding state, or claim
that an old binding governs a new commit. A binding mismatch remains `BLOCK` pending an explicit
maintainer recovery or a newer reviewed ATTUNE adapter.

## Release discipline

Before any tag, release, package publication, or visibility change:

- validate from native Windows and a portable clean checkout;
- build and smoke-test the wheel-installed adapter template;
- parse every tracked JSON file and validate schemas/fixtures;
- regenerate and verify `SCAFFOLD_MANIFEST.json`;
- scan staged history for secrets, private paths, generated state, and unexpected binaries;
- resolve or retain every focused-review finding;
- record the exact commit, tree, CI checks, and remaining limits;
- obtain a separate human decision for the exact external action.

Repository visibility is not package release. A Git tag is not PyPI publication. Technical `PASS`
is neither.
