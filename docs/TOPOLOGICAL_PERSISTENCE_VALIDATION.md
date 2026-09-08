# Topological persistence / restart validation

Status: **experimental BDR path validated; SQLite retained only as restart/parity oracle; not part of the RC7 storage path**.

Branch: `experiment/topological-temporal-memory-v1`

## Architecture

The persistence work is deliberately layered:

```text
Memoria.ia topological/temporal state
        |
        +-- SQLite snapshot adapter (oracle only)
        |
        +-- CtypesAtomicBDR
                |
                +-- BDR atomic C ABI
                        |
                        +-- AtomicDatabase / BDW4
```

SQLite is not the selected production architecture. It remains useful only as an independent comparison oracle while the BDR integration is validated.

## Persisted state

Both experimental representations preserve:

- deterministic reusable topological node addresses;
- node kind, canonical value and occurrence count;
- ordered composition components;
- graph edges;
- exact raw memories;
- temporal events and source metadata;
- transitions;
- internal monotonic next-sequence state;
- ingestion/new-node/reused-node counters.

The BDR mapping stores arbitrary binary records for nodes, raw provenance, events, transitions and a root manifest. The complete snapshot and root manifest are committed as one logical atomic BDR batch, so readers cannot observe a new root pointing to a partially persisted snapshot.

## Restart acceptance results

The persistence tests prove:

1. `CURRENT`, `HISTORY` and `STATE_DIFF` are structurally identical before and after reload.
2. Entity/value addresses remain identical across restart.
3. Raw input text reconstructs exactly after reload.
4. Address-space metrics remain identical after reload.
5. A timeline ending at explicit sequence `31` resumes at sequence `32` after restart.
6. The same representation works across car, sensor, server, robot and cat domains without persistence branches specific to those entities.
7. Missing referenced BDR records and empty SQLite snapshots fail closed.
8. The real BDR shared ABI reproduces the same topological/temporal fixture as the SQLite oracle after close/reopen.

## BDR host bridge validation

Resolutive-DB draft PR #26 exposes the existing atomic C ABI as a shared host library while retaining the static Android/C++ boundary.

Validated on Linux and Windows:

- shared-library build;
- real Python `ctypes` load;
- UTF-8 keys;
- arbitrary binary values;
- atomic multi-record write;
- close/reopen;
- exact byte round-trip;
- `last_sequence == durable_sequence` after durable batch;
- existing migration, crash-recovery, durability and Android gates remain green.

The Windows validation initially exposed Linux/POSIX-only headers in the broader v1 implementation. The correction was intentionally narrow: the shared AtomicDatabase target no longer links the unrelated legacy `database_v1.cpp`, and the BDW4 append/sync path uses platform wrappers (`open/write/fdatasync/close` on POSIX and `_open/_write/_commit/_close` on Windows). BDW4 framing and recovery semantics were not changed.

## Comparative benchmark evidence

Benchmark: `benchmarks/topological_persistence_benchmark.py`.

Recorded GitHub Actions fixture:

- observations: **240**;
- reusable nodes: **842**;
- raw memories: **240**;
- transitions: **216**;
- node reuse ratio: **0.9275**;
- branching factor: **2.8314**;
- duplicate deterministic addresses: **0**.

One recorded runner execution produced:

| Metric | SQLite oracle | BDR atomic |
|---|---:|---:|
| Save | 31.099 ms | 26.660 ms |
| Reload | 8.933 ms | 32.065 ms |
| Disk bytes | 1,040,384 B | 677,679 B |
| Post-reload query mean | 0.01781 ms | 0.01775 ms |
| Post-reload query p95 | 0.02049 ms | 0.01924 ms |

Additional fixture measurements:

- ingestion mean: **0.1425 ms**;
- ingestion p95: **0.1674 ms**;
- in-memory temporal query mean: **0.01766 ms**;
- in-memory temporal query p95: **0.02049 ms**.

Interpretation must remain workload-specific. In this run, BDR used materially less disk and saved slightly faster, while SQLite reloaded substantially faster. Query latency after reload was effectively equivalent because both backends reconstruct the same in-memory temporal structures before query resolution. These results are evidence, not a universal performance claim.

## Current conclusion

The earlier question “can the topological/temporal state survive restart?” is now answered positively for both the SQLite oracle and the BDR target path.

The stronger question “can BDR replace SQLite without changing Memoria.ia semantics?” is also answered positively for the current prototype fixture.

SQLite-specific development should stop here. Further persistence evolution should target the BDR adapter and public snapshot/catalog APIs rather than adding relational-schema features.

## Remaining before convergence/freeze

- remove adapter dependence on private `_nodes`, `_raw`, `_events`, `_transitions` and `_next_sequence` fields through public snapshot/catalog APIs;
- expand growth benchmarks across multiple corpus sizes rather than one fixed fixture;
- EvidenceCore provenance bridge preserving source/confidence/origin and LLM contamination barriers;
- Context Compiler integration producing compact cognitive packets;
- keep the full Linux/Windows baseline regression green after each convergence step.
