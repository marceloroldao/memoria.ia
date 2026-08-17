# v0.82 — Stability–plasticity frontier

## Purpose

Sweep the saturation cap introduced in v0.81 across several active→inactive→active regimes while also checking survival of a short contradictory burst.

## Preliminary local results

All tested caps survived a 3-step contradictory burst after 32 support observations and retained historical knowledge.

| max_strength | short-noise survival | mean deactivation steps | mean reactivation steps | mean online accuracy |
|---:|---:|---:|---:|---:|
| 1.25 | 1.0 | 12.00 | 1.00 | 0.8251 |
| 1.50 | 1.0 | 13.75 | 0.75 | 0.8096 |
| 2.00 | 1.0 | 15.75 | 0.75 | 0.7958 |
| 3.00 | 1.0 | 21.25 | 0.75 | 0.7498 |
| 4.00 | 1.0 | 24.00 | 0.50 | 0.7185 |

## Interpretation

In this deterministic probe, increasing the saturation cap monotonically reduces plasticity without improving short-noise survival. The current best region is therefore approximately 1.25–1.50, with 1.25 giving the fastest mean deactivation and highest mean online accuracy in this workload family.

This is not yet a final parameter choice. v0.83 must test stochastic noise, multiple seeds, burst-length variation, and regime-duration variation before a default is selected.
