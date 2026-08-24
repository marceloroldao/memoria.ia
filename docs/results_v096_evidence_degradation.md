# v0.96 Evidence-Degradation Result

This note records an equivalent local execution of `experiments/evidence_degradation_v96.py` for the current v0.96 branch.

## Setup

- 400 concepts arranged as 20 semantic families × 20 members;
- full scan as reference;
- discriminative routers with candidate limits 8, 16, 32 and 64;
- progressively degraded concept-specific evidence;
- acceptance threshold = 0.30;
- minimum margin = 0.03.

## Result

| retained evidence | limit | accuracy | parity vs full | abstention |
|---:|---:|---:|---:|---:|
| 1.00 | 8/16/32/64 | 1.00 | 1.00 | 0.00 |
| 0.75 | 8/16/32/64 | 1.00 | 1.00 | 0.00 |
| 0.50 | 8/16/32/64 | 1.00 | 1.00 | 0.00 |
| 0.25 | 8/16/32/64 | 0.00 | 1.00 | 1.00 |
| 0.00 | 8/16/32/64 | 0.00 | 1.00 | 1.00 |

The full scan showed the same transition: it resolved all queries with at least 50% concept-specific evidence and abstained when only family-level context remained.

## Interpretation

Within this controlled degradation benchmark, increasing the candidate limit above 8 does not recover information once the discriminative evidence is absent. The failure mode is therefore evidence insufficiency, not candidate pruning.

This supports keeping a small candidate set for well-separated cases while preserving conservative abstention when the query lacks concept-specific evidence.

The adaptive 8→16→32→64 router remains experimental. In this benchmark it has no expected recall advantage over fixed 8 because all fixed limits have identical parity with the full scan. Adaptive expansion should only be promoted if a broader corpus demonstrates cases where the correct concept falls outside the first 8 candidates while remaining recoverable by exact scoring.

## Scientific status

These are controlled synthetic results, not production or general-language claims. Broader natural-language corpora and repeated timing runs are still required before changing the default router.
