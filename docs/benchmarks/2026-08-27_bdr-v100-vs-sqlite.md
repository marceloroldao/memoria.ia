# Memoria.ia — direct native BDR v1.0.0 vs SQLite comparison

Date: 2026-08-27

## Scope

This experiment treats `marceloroldao/resolutive-DB` tag `v1.0.0` as an immutable external dependency. No BDR source is vendored or modified.

The final benchmark path is native C++ only. `benchmarks/bdr_v100_native_direct.cpp` calls the frozen `bdr::Database` API and the SQLite C API (`sqlite3`) directly in the same executable. The previous Python workload generator, serialized workload file and intermediary BDR driver were removed after the control tests.

Logical Memoria.ia-style records are materialized before the database timers start and the same records are supplied to both engines. The workload represents memory payloads, unique nodes and occurrence records. Materialization cost is reported separately and is not attributed to either database.

Durability boundaries for the bulk write/update/delete phases are matched at batch level: SQLite uses explicit transactions with `synchronous=FULL`; BDR uses asynchronous puts/erases followed by `sync()`. The test therefore measures batch-durable persistence rather than one-fsync-per-operation durability.

## Frozen dependency

- Repository: `marceloroldao/resolutive-DB`
- Exact version: `v1.0.0`
- API: frozen C++ `bdr::Database`
- BDR calls measured directly: `put`, `get`, `erase`, `sync`, `checkpoint`, `close`, reopen
- SQLite calls measured directly through `sqlite3`
- Build: Release, C++17, `-O3 -DNDEBUG`

CI verifies the exact `v1.0.0` tag before compiling.

## Heavy test matrix

| Case | Memories | Payload | Logical records | Random reads | Mutations |
|---|---:|---:|---:|---:|---:|
| Medium | 512 | 512 B | 647,271 | 100,000 | 50,000 |
| Heavy | 1,024 | 1,024 B | 2,426,088 | 250,000 | 100,000 |
| Very heavy | 2,048 | 1,024 B | 4,786,407 | 500,000 | 200,000 |

Every case completed writes, full sequential verification, random reads, updates, checkpoint, deletes, close/reopen and full post-reopen verification successfully.

## Direct native results

### Medium — 647,271 records

| Metric | SQLite | BDR v1.0.0 | SQLite / BDR |
|---|---:|---:|---:|
| Write | 1,151.418 ms | 863.369 ms | 1.33x |
| Sequential read | 2,964.746 ms | 211.447 ms | 14.02x |
| Random read | 793.403 ms | 68.028 ms | 11.66x |
| Update | 105.022 ms | 100.487 ms | 1.05x |
| Delete | 96.294 ms | 142.127 ms | 0.68x |
| Checkpoint | 14.831 ms | 3,063.305 ms | 0.005x |
| Reopen + verify | 3,588.179 ms | 569.169 ms | 6.30x |
| Disk | 51,654,656 B | 29,455,622 B | 1.75x |

Maximum RSS for the complete combined benchmark process: 398,184 KiB. Exit status: 0.

### Heavy — 2,426,088 records

| Metric | SQLite | BDR v1.0.0 | SQLite / BDR |
|---|---:|---:|---:|
| Write | 5,079.163 ms | 3,565.757 ms | 1.42x |
| Sequential read | 9,202.529 ms | 718.874 ms | 12.80x |
| Random read | 1,789.175 ms | 140.761 ms | 12.71x |
| Update | 226.811 ms | 150.684 ms | 1.51x |
| Delete | 263.011 ms | 426.553 ms | 0.62x |
| Checkpoint | 29.718 ms | 10,050.623 ms | 0.003x |
| Reopen + verify | 10,944.767 ms | 1,777.453 ms | 6.16x |
| Disk | 196,706,304 B | 110,743,314 B | 1.78x |

Maximum RSS for the complete combined benchmark process: 1,533,020 KiB. Exit status: 0.

### Very heavy — 4,786,407 records

| Metric | SQLite | BDR v1.0.0 | SQLite / BDR |
|---|---:|---:|---:|
| Write | 11,159.748 ms | 8,102.680 ms | 1.38x |
| Sequential read | 18,789.853 ms | 1,477.188 ms | 12.72x |
| Random read | 4,025.142 ms | 294.732 ms | 13.66x |
| Update | 491.945 ms | 339.635 ms | 1.45x |
| Delete | 633.234 ms | 967.986 ms | 0.65x |
| Checkpoint | 59.715 ms | 20,535.513 ms | 0.003x |
| Reopen + verify | 22,238.764 ms | 3,668.320 ms | 6.06x |
| Disk | 391,557,120 B | 219,519,962 B | 1.78x |

Post-reopen verification checked 4,686,407 expected surviving records. Maximum RSS for the complete combined benchmark process: 3,030,436 KiB. No swap was used. Exit status: 0.

## Interpretation

The direct native results remove the main uncertainty in the original comparison: the measured BDR operations no longer pass through Python, a serialized workload file or a subprocess driver.

Across all three sizes, BDR v1.0.0 consistently provides:

- about **1.33–1.42x faster batch-durable writes**;
- about **12.7–14.0x faster full sequential reads**;
- about **11.7–13.7x faster random reads**;
- about **1.05–1.51x faster update batches**;
- about **6.1–6.3x faster reopen plus complete verification**;
- about **43–44% lower measured disk footprint**.

Two important costs are also consistent and must be preserved in any integration decision:

1. **Delete batches are slower in BDR** in these workloads, roughly 1.5–1.6x slower than SQLite.
2. **BDR checkpoint is dramatically more expensive.** It grows from about 3.06 s at 647k records to 20.54 s at 4.79M records, while SQLite WAL checkpoint remains tens of milliseconds in this benchmark.

This suggests that BDR is attractive for the Memoria.ia access pattern when reads, reopen/recovery loading and storage footprint dominate, but a Memoria.ia integration must not checkpoint frequently on the foreground path. Checkpoint scheduling should be treated as a background/maintenance policy and validated separately.

## Status

The direct native performance experiment is successful and reproducible. It does **not** replace the current SQLite backend yet. Remaining integration gates include per-operation durable-write testing, explicit process-crash testing under a Memoria.ia-shaped workload, repeated checkpoint-churn policy tests and cross-platform validation. The frozen BDR v1.0.0 source remains unchanged throughout this experiment.
