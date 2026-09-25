# Memoria.ia v2.0.0-rc2 — cognitive-core freeze record

Status: functional freeze qualified; GitHub pre-release published 2026-09-25.

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

## Publication result

1. Package version `2.0.0rc2` and candidate-specific metadata passed on
   PR #363 without rewriting the RC1 citation, DOI or archived notes.
2. Historical RC1 publication no longer triggers on main push; the RC2
   publisher runs only by manual dispatch.
3. Publisher correction PR #364 passed its checks. The first publication run
   [36078715495](https://github.com/marceloroldao/memoria.ia/actions/runs/36078715495)
   failed before tag creation due to a literal newline escape in its freeze check.
4. The corrected publisher run
   [36079016388](https://github.com/marceloroldao/memoria.ia/actions/runs/36079016388)
   passed all steps. Public tag `v2.0.0-rc2` points to
   `e38f27b639bec1cfcb83694c1418a4d01f250ffd`, with a GitHub pre-release
   at https://github.com/marceloroldao/memoria.ia/releases/tag/v2.0.0-rc2.
5. Zenodo has not assigned an RC2 DOI. If archived there, add the assigned DOI
   after registration without moving the published tag.

No full natural-language understanding, unseen lexical paraphrase, universal
RAG superiority, complete OFF.IA end-to-end behavior or production security
certification is claimed by this freeze.
