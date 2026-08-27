# BDR v1.1 backend for Memoria.ia

This document records the measured and validated differences between SQLite and Resolutive-DB (BDR) v1.1.0 in the current Memoria.ia experimental Linux backend work. It is intentionally evidence-bound: the performance numbers below refer to the exact CI workloads described here and should not be generalized to unrelated workloads without new measurement.

## Current backend policy

- **Linux:** BDR v1.1.0 is the preferred experimental persistence backend when the native extension is available.
- **Fallback/control:** SQLite remains the behavioral reference and fallback backend.
- **Windows/macOS:** SQLite remains the practical fallback until the native BDR integration is portable and packaged for those platforms.
- **Main branch:** this policy is still staged through experimental PRs; it is not a blanket production claim.

## Correctness difference that motivated v1.1

A single logical Memoria.ia memory is materialized as several physical records: payload, nodes, occurrences and metadata.

BDR v1.0.0 had durable `sync()` semantics but no atomic multi-key batch. A crash during one logical add could therefore leave partial logical state.

BDR v1.1.0 adds `AtomicDatabase`, BDW4 and atomic `write_batch`/bulk operations. The accepted Memoria.ia contract is now:

```text
1 logical Memoria.ia memory
        =
1 atomic BDR batch / sequence
        =
all committed or all absent after recovery
```

Atomicity and durability are separate:

- `BatchSync`: atomic + durable at the batch boundary;
- `Async`: atomic logical batch, durability may lag;
- later `sync()`: advances durability without changing the already established logical batch boundaries.

The safe default remains one durability boundary per logical memory. Deferred durability is an explicit performance policy.

## End-to-end measured results

### Durable after every logical memory

Workload: 256 memories × 512-byte payloads.

| Metric | SQLite | BDR v1.1 | Observed difference |
|---|---:|---:|---:|
| Write | 9.847 s | 0.693 s | BDR 14.20× faster |
| Reconstruct/read pass | 3.393 ms | 0.363 ms | BDR 9.35× faster |

Logical statistics matched exactly.

### Deferred durability (`sync_every_memories=16`)

Workload: 1,024 memories × 1,024-byte payloads.

| Metric | SQLite | BDR v1.1 | Observed difference |
|---|---:|---:|---:|
| Write | 107.458 s | 5.560 s | BDR 19.33× faster |
| Reconstruct/read pass | 13.917 ms | 1.808 ms | BDR 7.70× faster |

Logical statistics matched exactly.

## Validation gates passed

The BDR v1.1 native workflow validated:

- exact checkout/build of the published `v1.1.0` tag;
- native Memoria.ia extension build;
- BDR/SQLite behavioral equivalence;
- one logical-memory add advancing one atomic sequence under the default policy;
- torn final `atomic.bdw4` recovery dropping the entire incomplete logical memory while preserving the previously committed memory and metadata;
- reopen and durable-sequence preservation;
- full Memoria.ia regression: **431 passed** in the native BDR workflow.

The generic experimental regression also passed on Ubuntu and Windows after making the POSIX-only `0600` file-mode assertion platform-correct.

## Operational differences

### SQLite

Advantages:

- portable and widely packaged;
- mature SQL/tooling ecosystem;
- useful control backend for equivalence testing;
- no native BDR build dependency.

Current role in Memoria.ia:

- fallback;
- portability path;
- behavioral reference/control.

### BDR v1.1

Advantages demonstrated in the measured Memoria.ia workloads:

- substantially lower write and read latency;
- atomic logical-memory batch persistence;
- explicit atomicity/durability separation;
- native key/value storage aligned with Memoria.ia's record model.

Current caveats:

- native integration is Linux-first;
- installable/stable consumer packaging still needs improvement;
- cross-process multi-writer mode is intentionally not enabled by Memoria.ia;
- checkpoint/maintenance telemetry remains a BDR roadmap item;
- delete-heavy performance and memory telemetry remain follow-up areas.

## Direct-binding follow-up

The first v1.1 integration used a compatibility shim so the existing v1.0-oriented pybind layer could be validated with minimal risk. The next experiment removes that shim and binds directly to `AtomicDatabase`.

The desired direct contract is:

```text
logical add #1 -> atomic sequence N     (Async or BatchSync)
logical add #2 -> atomic sequence N+1   (Async or BatchSync)
logical add #3 -> atomic sequence N+2   (Async or BatchSync)
```

With deferred durability, the durable sequence may lag until `sync()`, but the logical batch boundaries must remain distinct. This is preferable to grouping several logical memories into one larger atomic transaction merely because durability is deferred.

Related tracking: issue #30, issue #33, PR #29, PR #31 and merged PR #32.