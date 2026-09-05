# Memoria.ia — direct native BDR v1.0.0 vs SQLite comparison

Date: 2026-08-27

## Scope

This experiment treats `marceloroldao/resolutive-DB` tag `v1.0.0` as an immutable external dependency. No BDR source is vendored or modified.

The final benchmark path is native C++ only. `benchmarks/bdr_v100_native_direct.cpp` calls the frozen `bdr::Database` API and the SQLite C API (`sqlite3`) directly in the same executable. The previous Python workload generator, serialized workload file and intermediary BDR driver were removed after the control tests.

Logical Memoria.ia-style records are materialized before the database timers start and the same records are supplied to both engines. The workload represents memory payloads, unique nodes and occurrence records. Materialization cost is reported separately and is not attributed to either database.

Durability boundaries for the bulk write/update/delete phases are matched at batch level: SQLite uses explicit transactions with `synchronous=FULL`; BDR uses asynchronous puts/erases followed by `sync()`. Separate resilience gates measure one-durable-write-per-operation behavior, forced process termination, repeated checkpoints and portability.

## Frozen dependency

- Repository: `marceloroldao/resolutive-DB`
- Exact version: `v1.0.0`
- API: frozen C++ `bdr::Database`
- BDR calls measured directly: `put`, `put_sync`, `get`, `erase`, `sync`, `checkpoint`, `close`, reopen
- SQLite calls measured directly through `sqlite3`
- Build: Release, C++17

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

Post-reopen verification checked 4,686,407 expected surviving records. No data mismatch was observed.

## Resilience and durability gates

### Per-operation durable writes

The direct resilience executable performed 5,000 writes of 256-byte values with one durability boundary per operation.

| Engine | Time | Relative |
|---|---:|---:|
| SQLite WAL + `synchronous=FULL` autocommit | 2,782.90 ms | 1.00x |
| BDR `put_sync` | 7,405.04 ms | 2.66x slower |

Both engines passed close/reopen and complete value verification. BDR also preserved the expected `durable_sequence`.

This is an important negative result: BDR's strong performance in the heavy benchmark depends on batching durability. A Memoria.ia integration should not call `put_sync` for every logical record unless that latency is explicitly required.

### Repeated checkpoint churn

The churn gate executed 40 cycles × 5,000 operations = 200,000 accepted mutations over a 20,000-key space. Every cycle performed checkpoint, close/reopen and full oracle verification.

| Metric | SQLite | BDR v1.0.0 |
|---|---:|---:|
| Cycles | 40 | 40 |
| Accepted mutations | 200,000 | 200,000 |
| Final live records | 14,993 | 14,993 |
| Cumulative checkpoint time | 759.714 ms | 1,583.26 ms |

Both engines passed all 40 reopen/oracle checks. BDR checkpoint cost was about 2.08x SQLite in this smaller repeatedly compacted workload. This is consistent with the earlier observation that checkpoint is a BDR cost center, although the absolute penalty is much smaller here than on the multi-million-record one-shot benchmark.

### Forced process crash recovery

The crash gate intentionally terminates the writer with `std::_Exit(99)` without `close()` or destructors.

BDR test:

- 20,000 records were written and explicitly `sync()`ed;
- 10,000 additional records were submitted without the final explicit sync;
- after hard termination and reopen, all 20,000 guaranteed-durable records were present and correct;
- 6,079 of the 10,000 unsynced suffix records also survived, all with correct values;
- no corruption of the durable prefix or surviving suffix was observed.

SQLite control:

- a 20,000-record committed prefix survived correctly;
- a 10,000-record uncommitted transaction was terminated before commit;
- zero records from the uncommitted suffix were exposed after reopen.

The BDR result means the durability contract must be interpreted precisely: after `sync()`/`put_sync`, data is guaranteed by this gate; before that boundary, records may or may not survive because batching/background WAL persistence can make part of the suffix durable. Applications must not assume that unsynced writes are guaranteed to disappear.

## Cross-platform frozen-v1 validation

The exact frozen source was configured and compiled without source modification.

| Platform | Result | Finding |
|---|---|---|
| Ubuntu 24.04 | PASS | `v1_candidate_contract` compiled and passed. |
| macOS 26 ARM64 | FAIL to build | `database_v1.cpp` directly includes `<linux/falloc.h>`. |
| Windows Server 2025 / MSVC | FAIL to build | After ZLIB was provisioned successfully and CMake configured, the same `<linux/falloc.h>` include stopped compilation. |

Therefore BDR v1.0.0 is currently Linux-specific at source level. The Windows failure was re-tested after installing ZLIB through vcpkg, so it is not merely a missing dependency. Portability requires a future BDR change that abstracts Linux-specific allocation/filesystem calls instead of including Linux headers unconditionally.

## Interpretation

Across all three heavy direct-native sizes, BDR v1.0.0 consistently provides:

- about **1.33–1.42x faster batch-durable writes**;
- about **12.7–14.0x faster full sequential reads**;
- about **11.7–13.7x faster random reads**;
- about **1.05–1.51x faster update batches**;
- about **6.1–6.3x faster reopen plus complete verification**;
- about **43–44% lower measured disk footprint**.

The resilience gates refine that conclusion substantially:

1. **Linux durability/recovery behavior passed the tested gates.** Explicitly synchronized data survived hard process termination correctly.
2. **Per-operation durability is expensive.** BDR `put_sync` was about 2.66x slower than SQLite FULL autocommit in the 5,000-operation gate.
3. **Checkpoint remains a cost center.** Repeated churn passed, but cumulative BDR checkpoint time was about 2.08x SQLite; at multi-million-record scale the earlier one-shot checkpoint penalty was much larger.
4. **Delete batches remain slower in BDR** in the heavy workload.
5. **BDR v1.0.0 is not currently portable beyond Linux** because the frozen implementation contains an unconditional Linux header dependency.

For Memoria.ia, the technically appropriate BDR usage pattern is therefore batch-oriented persistence with explicit durability boundaries and infrequent/background checkpoints. A one-fsync-per-logical-record policy would discard much of BDR's performance advantage.

## Status

The direct-native performance, per-operation durability, forced-process-crash recovery and repeated checkpoint-churn gates are complete on Linux. Ubuntu contract validation passes. macOS and Windows portability gates correctly expose a source-level Linux dependency in frozen BDR v1.0.0.

This evidence is sufficient to continue toward a Linux-first experimental Memoria.ia BDR backend, while keeping SQLite as the control/fallback backend. Before any default-backend replacement, the remaining engineering work should include a common storage interface, integration-level crash tests inside Memoria.ia itself, checkpoint scheduling policy, and a future portable BDR release for Windows/macOS support.
