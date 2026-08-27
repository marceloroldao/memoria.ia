# BDR v1.1 backend for Memoria.ia

This document records the measured and validated differences between SQLite and Resolutive-DB (BDR) v1.1.0 in the current Memoria.ia experimental Linux backend work. Performance numbers are tied to the exact CI workloads below and should not be generalized without new measurements.

## Current backend policy

- **Linux:** BDR v1.1.0 is the preferred experimental persistence backend when the native extension is available.
- **Fallback/control:** SQLite remains the behavioral reference and fallback backend.
- **Windows/macOS:** SQLite remains the practical fallback until native BDR portability and packaging are completed.
- **Main branch:** adoption is still staged through PR #31; this document does not itself promote the backend to `main`.

## Correctness contract

A single logical Memoria.ia memory is materialized as several physical records: payload, nodes, occurrences and metadata.

BDR v1.0.0 had durable `sync()` semantics but no atomic multi-key batch. BDR v1.1.0 adds `AtomicDatabase`, BDW4 and atomic batch operations. The accepted contract is:

```text
1 logical Memoria.ia memory
        =
1 atomic BDR batch / sequence
        =
all committed or all absent after recovery
```

Atomicity and durability are deliberately separate:

- `BatchSync`: one atomic logical batch that is durable at return;
- `Async`: one atomic logical batch whose durability may lag;
- later `sync()`: advances durability without merging or changing the already established logical batch boundaries.

Therefore `sync_every_memories > 1` means deferred durability, **not** grouped logical atomicity. Each memory still receives its own atomic sequence.

## Current direct-binding results

The compatibility shim used for the first v1.1 acceptance has been replaced by a direct pybind11 binding to `bdr::AtomicDatabase` after passing correctness, crash-recovery and performance gates.

### Durable after every logical memory

Workload: 256 memories × 512-byte payloads.

| Metric | SQLite | BDR v1.1 direct | Observed difference |
|---|---:|---:|---:|
| Write | 9.856 s | 0.488 s | BDR **20.22× faster** |
| Reconstruct/read pass | 2.907 ms | 0.336 ms | BDR **8.66× faster** |

Logical statistics matched exactly.

### Deferred durability (`sync_every_memories=16`)

Workload: 1,024 memories × 1,024-byte payloads. Each of the 16 logical memories remains a separate atomic batch; only durability is grouped.

| Metric | SQLite | BDR v1.1 direct | Observed difference |
|---|---:|---:|---:|
| Write | 107.934 s | 3.073 s | BDR **35.12× faster** |
| Reconstruct/read pass | 11.725 ms | 1.532 ms | BDR **7.65× faster** |

Logical statistics matched exactly.

## Direct binding vs initial v1.1 compatibility shim

The initial shim was intentionally conservative and accumulated pending writes before translating them to `AtomicDatabase`. The direct binding removes that compatibility layer and preserves one sequence per logical memory even when durability is deferred.

| Workload | v1.1 shim BDR write | v1.1 direct BDR write | Direct-binding gain |
|---|---:|---:|---:|
| sync/1, 256 × 512 B | 0.693 s | 0.488 s | **~1.42×** |
| sync/16, 1,024 × 1,024 B | 5.560 s | 3.073 s | **~1.81×** |

Read/reconstruct also improved modestly in these runs (0.363 → 0.336 ms for sync/1 and 1.808 → 1.532 ms for sync/16), but runner variation means write-path and semantic improvements are the stronger conclusions.

## Validation gates passed

The direct BDR v1.1 native workflow validated:

- exact checkout/build of published BDR `v1.1.0`;
- direct `AtomicDatabase` pybind extension build;
- BDR/SQLite behavioral equivalence;
- one logical-memory add advancing one atomic sequence;
- deferred durability with **distinct atomic sequences per memory** and lagging durable sequence until the sync boundary;
- torn final `atomic.bdw4` recovery dropping the entire incomplete logical memory while preserving the previously committed memory and metadata;
- reopen and durable-sequence preservation;
- full Memoria.ia regression: **432 passed**;
- both end-to-end benchmark workloads passed and produced exact logical statistics.

The generic experimental regression also passes on Ubuntu and Windows; Windows currently exercises the fallback/non-BDR path.

## Operational differences

### SQLite

Advantages:

- portable and widely packaged;
- mature SQL/tooling ecosystem;
- useful control backend for equivalence testing;
- no native BDR build dependency.

Current role:

- fallback;
- portability path;
- behavioral reference/control.

### BDR v1.1 direct

Advantages demonstrated in the measured Memoria.ia workloads:

- substantially lower write/read latency;
- atomic logical-memory persistence;
- atomicity independent from durability cadence;
- native key/value model aligned with Memoria.ia's physical records;
- no compatibility shim in the hot path.

Current caveats:

- native integration remains Linux-first;
- stable/installable consumer packaging still needs improvement (tracked on the BDR side);
- cross-process multi-writer mode is intentionally not enabled by Memoria.ia;
- checkpoint/maintenance telemetry remains a BDR roadmap item;
- delete-heavy performance and memory telemetry remain follow-up areas;
- the direct binding currently maps Memoria.ia `checkpoint()` to a durable sync because `AtomicDatabase` v1.1 does not expose a checkpoint primitive.

## Current direct integration shape

```text
logical add #1 -> atomic sequence N     -> Async or BatchSync
logical add #2 -> atomic sequence N+1   -> Async or BatchSync
logical add #3 -> atomic sequence N+2   -> Async or BatchSync
                                   \
                                    later sync() advances durable_sequence
```

This is now the preferred experimental BDR integration shape for Memoria.ia.

Related tracking: issue #30, issue #33, PR #29, PR #31, merged PR #32, and Resolutive-DB issues #9/#14.