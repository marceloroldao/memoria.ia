# Memoria.ia — BDR v1.0.0 vs SQLite persistence comparison

Date: 2026-08-27

## Scope

This experiment treats `marceloroldao/resolutive-DB` tag `v1.0.0` as an immutable external baseline. No BDR source is vendored or modified.

The current Memoria.ia persistence baseline is `SQLiteResolutiveMemory`, which stores three logical families:

- memory payloads;
- unique resolutive nodes;
- occurrences linking memory/layer/local-time to nodes.

A direct comparison of the full SQLite store against a plain BDR key/value operation would be misleading. The experiment therefore reports two views:

1. **Current Memoria SQLite end-to-end** — the existing `SQLiteResolutiveMemory.add()` and `reconstruct()` path, including chunking, digest calculation and relational inserts.
2. **Storage-only equivalent workload** — both SQLite and frozen BDR v1.0.0 receive the exact same pre-materialized logical records representing memories, unique nodes and occurrences.

Performance values are evidence only. Correctness and full reopen verification are hard gates.

## Frozen dependency

- Repository: `marceloroldao/resolutive-DB`
- Version: `v1.0.0`
- API used: frozen C++ `bdr::Database` surface (`put`, `get`, `sync`, `checkpoint`, `close`, reopen)
- BDR options: v1.0.0 defaults, unchanged

The CI explicitly checks out tag `v1.0.0` before building the static `bdr::bdr` implementation.

## Initial workload

- Memories: 256
- Payload per memory: 256 bytes
- Maximum resolutive layer: 3
- Materialized logical records: 173,878
- Logical value payload: 4,282,328 bytes
- Logical materialization time: 255.395 ms

All records were verified after initial writes and again after closing/reopening each database.

## Results

| Metric | Current Memoria SQLite | SQLite logical-only | BDR v1.0.0 logical-only |
|---|---:|---:|---:|
| Write | 5,584.023 ms | 318.603 ms | 193.115 ms |
| Read | 3.399 ms | 1,066.084 ms | 40.943 ms |
| Reopen + full verify | 3.592 ms | 1,251.866 ms | 94.750 ms |
| Disk bytes | 21,422,080 | 16,748,544 | 9,896,944 |

For the equivalent storage-only workload, BDR v1.0.0 was approximately:

- **1.65x faster** on batched writes;
- **26.0x faster** on full key reads;
- **13.2x faster** on reopen plus full verification;
- **40.9% smaller** in measured on-disk bytes.

## Interpretation

The result is sufficient to justify continuing BDR as a candidate persistence backend for Memoria.ia, but it is not yet sufficient to replace SQLite.

The 5.584 s current Memoria SQLite write time includes higher-level work and many relational operations that are intentionally excluded from the storage-only comparison. Consequently, the large difference between current end-to-end SQLite and BDR storage time must not be presented as a direct engine speedup.

The meaningful first conclusion is narrower: **when both engines persist the same pre-materialized Memoria.ia logical record set, frozen BDR v1.0.0 is materially faster and smaller on this initial workload while preserving complete reopen correctness.**

## Next validation gates

Before any backend replacement decision, repeat the comparison across multiple workload sizes and add:

- durable-write profiles, not only batched durability;
- checkpoint/reopen cycles;
- process-crash recovery;
- repeated update/delete workloads;
- multiwriter/concurrency where applicable;
- memory/RSS measurements;
- Windows validation if the BDR build path is available there;
- an actual Memoria.ia BDR adapter behind a common storage interface, while keeping SQLite available as the control backend.

Until those gates pass, BDR remains an experimental external backend candidate and SQLite remains the current Memoria.ia implementation.
