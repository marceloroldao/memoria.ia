# v0.70 — Packed lifecycle

v0.70 replaces per-layer lists of transition tuples with transition counters plus only the most recent transition. Functional state dynamics remain unchanged.

## Controlled contradictory workload

Workload: 100,000 events, 5,000 items, 5 layers, deterministic seed 11.

| Mode | Mean-like single-run latency/event | Peak traced memory | Transitions |
|---|---:|---:|---:|
| Compact v0.62 | 10.18 us | 9.32 MB | 41,784 |
| Packed v0.70 | 7.40 us | 4.25 MB | 41,784 |

Observed change in this run:

- latency/event: about 27% lower;
- peak traced memory: about 54% lower;
- transition count: identical.

## Functional regression

The packed representation is required to match CompactMemoryLifecycle for:

- active depth;
- historical depth;
- per-layer strength/state snapshots;
- transition counts;
- deconsolidation;
- reactivation;
- layer-local rate rule `r_L = 2^-L`.

## Tradeoff

Packed mode is an operational representation, not a full provenance mode. It preserves aggregate transition counts and the latest transition per layer, but does not preserve the complete chronological transition list. Full provenance remains a separate optional capability.

## Decision

The v0.70 direction is retained. Next maturity gate is persistence/recovery (v0.75), including round-trip restoration of packed state and corruption-safe storage tests.

These are experimental Python measurements and should not be treated as production benchmark claims.
