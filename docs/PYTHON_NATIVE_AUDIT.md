# Python ↔ Native Authority Audit

Status: P0 migration completed by Issue #88; native resolve scaling follow-up is tracked separately in Issue #110.

## Objective

Converge Android, Windows, Linux and PC/server on one authoritative Memoria.ia native runtime while keeping Python for FastAPI, Pydantic, provider adapters, administration, tests and orchestration.

The migration rule is: **one authoritative semantic implementation, multiple thin product boundaries**.

## Current authority map

| Capability | Authoritative/current native path | Python role / remaining work |
| --- | --- | --- |
| Semantic candidate ranking + confidence | `native/mobile/semantic_kernel.c` | Python implementation is reference/parity only and is not imported by native production startup |
| Relation extraction | `native/mobile/relation_extractor.c` | Python parser is reference/parity only |
| Trajectory/window resolve | `native/mobile/trajectory_*` | Python retains tests/orchestration |
| Temporal previous/current | `native/mobile/temporal_state_*` | Production conversation route delegates to native runtime |
| Episodic recall | `native/mobile/episodic_kernel.c` | Python episodic service is reference-only unless `MEMORIA_EPISODIC_RUNTIME=python` is explicitly selected |
| Turn persistence | `native/mobile/mobile_persistence_bdr.c` | BDR is authoritative persistence for native runtime |
| Persistent namespaces | native turn `namespace` | Server maps product `session_id` to namespace; OFF.IA omits namespace and retains global personal memory |
| Correction/supersession | native learn/persistence boundary | Python implementation is reference/parity only |
| Provenance/authority lineage | native parent/root lineage + supersession metadata | `memory_provenance.py` is not imported by native production conversation startup |
| Relation identity | persisted native relation memory IDs | Thin server adapter pre-computes bounded deterministic IDs; native extraction decides how many are consumed |
| Native process ownership | `native_runtime.py` shared DLL/handle/lock manager | Python owns lifecycle only; semantic state remains inside one native runtime/store |
| Episodic server adapter | `NativeEpisodicService` | FastAPI/Pydantic remain Python |
| Conversation server adapter | `NativeConversationService` | FastAPI/Pydantic/auth remain Python; semantic work is native |

## Product boundaries

### OFF.IA

`OFF.IA -> Memoria.ia native/mobile ABI -> Resolutive-DB`

OFF.IA must not parse BDR, duplicate semantic rules, or use product-server namespaces for its persistent personal memory. Its `session_id` continues to describe the active conversation window/trajectory.

### PC/server

`FastAPI/Pydantic -> neutral HTTP contract -> thin native adapter -> shared native runtime -> Memoria.ia native core -> Resolutive-DB`

Server `session_id` maps to native persistent `namespace` for product-level conversation isolation.

## Completed parity/acceptance slices

- semantic factual/reference vectors;
- correction and supersession;
- provenance root protection against generated echoes;
- multi-source trajectory;
- temporal previous/current native acceptance;
- episodic Python/native parity;
- episodic session isolation;
- opt-in native episodic HTTP adapter;
- persistent relation IDs;
- persistent turn namespace isolation;
- native parent lineage, authority clamping and superseded-by metadata;
- opt-in native conversation HTTP adapter;
- shared product relation extraction parity for compact Portuguese copulas, elliptic relations, dedupe and noise filtering;
- deliberate native English `is` compound-subject compatibility preserved for mobile/temporal entities;
- complete supported conversation response parity, including native-authoritative confidence, durable relation order/time metadata, corrections, fallback, unresolved and restart;
- shared server native runtime manager with one DLL/handle/lock, reference-counted leases and joint conversation/episodic restart recovery;
- native server production default with fail-closed library requirement and a Docker image that proves native conversation/episodic persistence across restart;
- Python reference semantics isolated from native production startup; explicit Python mode remains parity/reference only;
- fixed 256-turn native capacity removed with geometric dynamic allocation and a 300-turn BDR restart regression;
- reproducible native production benchmark matrix completed and versioned at 100 / 1,000 / 10,000 records.

## Accepted native benchmark matrix

GitHub Actions run `33270148076`, PR #109, pinned Resolutive-DB `1f6b7ccbe16bdfed2f1b5dcebceb17887bf6916e`.

| records | ingest p50 | ingest p95 | resolve p50 | resolve p95 | RSS peak | restart/load | selected context |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 0.414567 ms | 0.571824 ms | 0.135134 ms | 0.194920 ms | 45.477 MiB | 2.926600 ms | 25 B |
| 1,000 | 0.439418 ms | 0.585933 ms | 5.086863 ms | 6.687028 ms | 55.723 MiB | 18.668047 ms | 25 B |
| 10,000 | 0.444959 ms | 0.594831 ms | 693.232709 ms | 710.630051 ms | 226.934 MiB | 218.140401 ms | 25 B |

All semantic and restart validations passed for all three sizes. Raw JSON is versioned under `benchmarks/results/native-server/`.

The benchmark does **not** establish a performance-superiority claim. It exposes a resolve-scaling bottleneck at 10k while showing nearly flat ingest latency. That optimization is deliberately separated from the authority migration and tracked in Issue #110. Current code repeatedly traverses lineage and performs full-array memory lookup while materializing candidates, producing an effectively quadratic hot path at scale.

## Issue #88 acceptance

The migration acceptance criteria are satisfied:

- shared native C ABI is authoritative;
- Android, Ubuntu and Windows gates are green;
- BDR persistence/restart is green;
- cross-runtime parity is green for supported contracts;
- benchmark evidence is reproducible and versioned;
- HTTP/ABI compatibility is preserved;
- native production startup does not load a second authoritative Python ranking/provenance implementation.

Issue #88 can therefore be closed after PR #109 merges. Performance work continues independently in #110 without weakening semantic correctness or changing the migration authority boundary.
