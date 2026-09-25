# Memoria.ia v2.0.0-rc2 — cognitive-core freeze record

Status: functional freeze qualified; release publication pending.

## Immutable functional baseline

- Functional freeze branch: `freeze/v2.0.0-rc2-cognitive-core`
- Functional freeze commit: `e240bf2197000f955d65edec5dba47045d9f237e`
- Published BDR dependency: `v1.2.0-rc4` at `317882a00f041fc1568ff986af8016b09453f21a`
- Previous Memoria.ia release: `v2.0.0-rc1`, DOI `10.5281/zenodo.22908785`

The merged commit has the same file tree as the validated PR #361 head
`ead13b81ad1dbc793e29c8097540b4469f044738`. Freeze and RC1 history
must not be moved or overwritten. Publication-only commits must not change
the cognitive runtime or BDR pin.

## Evidence against the published BDR pin

| Gate | PR head run | Result |
| --- | --- | --- |
| Android mobile ABI host and arm64 | [36077501782](https://github.com/marceloroldao/memoria.ia/actions/runs/36077501782) | PASS |
| Shared BDR cold reopen | [36077501787](https://github.com/marceloroldao/memoria.ia/actions/runs/36077501787) | PASS |
| Product-alpha, full tests, Docker, restart, backup/restore, R14 | [36077501751](https://github.com/marceloroldao/memoria.ia/actions/runs/36077501751) | PASS |
| RC1 archival metadata preservation | [36077501753](https://github.com/marceloroldao/memoria.ia/actions/runs/36077501753) | PASS |
| Product application credentials | [36077501784](https://github.com/marceloroldao/memoria.ia/actions/runs/36077501784) | PASS |
| v0.96 semantic validation | [36077501755](https://github.com/marceloroldao/memoria.ia/actions/runs/36077501755) | PASS |
| Layered performance baseline | [36077501760](https://github.com/marceloroldao/memoria.ia/actions/runs/36077501760) | PASS |
| Experimental PR regression | [36077501798](https://github.com/marceloroldao/memoria.ia/actions/runs/36077501798) | SKIPPED by branch condition; not claimed as a pass |

BDR itself passed CI run 36062508821 and RC4 validation run 36062508908
on its published commit. The R1–R14 scope and limitations are detailed in
`docs/V2_NEXT_RC_FREEZE_AUDIT.md` and `docs/V2_POST_RC1_RECONCILIATION.md`.

## Publication gates still pending

1. Stage package version `2.0.0rc2` and a candidate-specific metadata gate
   without rewriting the RC1 citation, DOI or archived release notes.
2. Ensure the historical RC1 publisher cannot run on RC2 metadata changes.
3. Run the full release candidate CI on the final publication commit.
4. Create the GitHub pre-release tag on that exact green commit, then verify
   the tag, release notes and source archive.
5. If archiving on Zenodo, add the assigned RC2 DOI after registration without
   moving the tag. No RC2 DOI is claimed in this staging record.

No full natural-language understanding, unseen lexical paraphrase, universal
RAG superiority, complete OFF.IA end-to-end behavior or production security
certification is claimed by this freeze.
