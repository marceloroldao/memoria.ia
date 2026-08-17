# v0.94 — Incompressible payload and integrated persistence audit

Status: pre-release audit. This is not yet the v0.95 release candidate.

## Goal

Challenge the v0.93 compact snapshot with low-repetition payloads so the compression result is not dominated by repeated semantic content.

Each knowledge node receives a pseudo-random 256-byte hexadecimal payload while route/lifecycle structure remains representative of the v0.92/v0.93 benchmark. Four routes are registered per knowledge node.

## Local benchmark

| Knowledge | Routes | Verbose snapshot | Compact snapshot | Reduction | Compact bytes/route |
|---:|---:|---:|---:|---:|---:|
| 100 | 400 | 323,866 B | 19,879 B | 93.86% | 49.70 B |
| 500 | 2,000 | 1,623,066 B | 94,111 B | 94.20% | 47.06 B |
| 1,000 | 4,000 | 3,247,066 B | 184,926 B | 94.30% | 46.23 B |
| 5,000 | 20,000 | 16,279,066 B | 914,547 B | 94.38% | 45.73 B |

The reduction is lower than the ~98.8% seen in the highly repetitive v0.93 corpus, as expected, but compact storage remains substantially smaller because the routed lifecycle representation itself contains repeated structure.

## CPU trade-off

At 5,000 knowledge nodes / 20,000 routes in the local run:

- verbose encode: ~292 ms;
- compact encode: ~590 ms;
- raw zlib decompression alone: ~19 ms.

Full object reconstruction costs more than decompression alone and must continue to be measured separately. The compact format is therefore primarily a storage/transmission optimization, not a low-latency serialization optimization.

## Interpretation

The v0.93 headline result must not be generalized as a universal 98.8% compression ratio. On low-repetition payloads in this controlled benchmark, a more defensible observed result is approximately 94% reduction, with the exact ratio depending on payload entropy, trajectory structure, and lifecycle state.

## Release-candidate implications

The compact format passes the size robustness check. Remaining v0.95 gates are integrated regression coverage, package/import consistency, public API documentation, reproducibility instructions, license/CITATION audit, known-limitations documentation, and final review of compatibility with the central Resolutive specification where applicable.
