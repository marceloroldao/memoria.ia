# Python ↔ Native Authority Audit

Status: active P0 migration tracker for Issue #88.

## Objective

Converge Android, Windows, Linux and PC/server on one authoritative Memoria.ia native runtime while keeping Python for FastAPI, Pydantic, provider adapters, administration, tests and orchestration.

The migration rule is: **one authoritative semantic implementation, multiple thin product boundaries**.

## Current authority map

| Capability | Authoritative/current native path | Python role / remaining work |
| --- | --- | --- |
| Semantic candidate ranking + confidence | `native/mobile/semantic_kernel.c` | Python parity/reference code remains temporarily aligned until server migration completes |
| Relation extraction | `native/mobile/relation_extractor.c` | Shared product vectors are parity-gated; Python parser remains the default server path until native conversation becomes default |
| Trajectory/window resolve | `native/mobile/trajectory_*` | Python retains tests/orchestration |
| Temporal previous/current | `native/mobile/temporal_state_*` | Exposed through opt-in native conversation runtime |
| Episodic recall | `native/mobile/episodic_kernel.c` | `NativeEpisodicService` is opt-in; Python remains default during migration |
| Turn persistence | `native/mobile/mobile_persistence_bdr.c` | BDR is authoritative persistence for native runtime |
| Persistent namespaces | native turn `namespace` | Server maps product `session_id` to namespace; OFF.IA omits namespace and retains global personal memory |
| Correction/supersession | native learn/persistence boundary | Python implementation remains until production conversation route switches |
| Provenance/authority lineage | native parent/root lineage + supersession metadata | Python `memory_provenance.py` remains a reference/legacy server path during migration |
| Relation identity | persisted native relation memory IDs | Server may pre-compute bounded deterministic IDs; native extraction decides how many are consumed |
| Native process ownership | `native_runtime.py` shared DLL/handle/lock manager | Python owns lifecycle only; semantic state remains inside one native runtime/store |
| Episodic server adapter | `NativeEpisodicService` | FastAPI/Pydantic remain Python |
| Conversation server adapter | `NativeConversationService` | FastAPI/Pydantic/auth remain Python; runtime remains opt-in until production-default slice |

## Product boundaries

### OFF.IA

`OFF.IA -> Memoria.ia native/mobile ABI -> Resolutive-DB`

OFF.IA must not parse BDR, duplicate semantic rules, or use product-server namespaces for its persistent personal memory. Its `session_id` continues to describe the active conversation window/trajectory.

### PC/server

`FastAPI/Pydantic -> thin native adapter -> shared native runtime -> Memoria.ia native core -> Resolutive-DB`

Server `session_id` may be mapped to native persistent `namespace` to preserve product-level conversation isolation.

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
- complete supported conversation response parity, including native-authoritative confidence, durable relation order/time metadata, corrections, fallback, unresolved and restart.

## Current slice — shared native runtime lifecycle

The conversation and episodic adapters previously each loaded `libmemoria_mobile`, opened an independent native handle and owned a separate lock/close lifecycle. The product server also placed those stores in separate directories. This slice removes that duplicated process ownership.

Design decisions:

- `NativeRuntimeManager` owns one DLL, one `memoria_mobile_open` handle and one re-entrant lock per canonical `(library_path, data_dir, organization_id)`;
- leases are reference-counted; closing one service releases only its lease, while the last release closes the native handle;
- opening the same active store with a different native library fails closed;
- conversation and episodic services delegate call/flush/lifecycle to the manager and do not own native ABI setup independently;
- when both product runtimes are native, the server points both adapters at one `native-runtime` store so turns and episodes share one durable BDR-backed handle;
- when only one feature is native, its existing `native-conversation` or `native-episodic` path is preserved;
- if both runtimes are enabled and a legacy split store already contains data, startup fails explicitly instead of silently abandoning or merging persistent state. A future migration must be deliberate.

Acceptance requirements:

- conversation and episodic adapters acquired for the same store share one exact native runtime object;
- releasing one adapter leaves the other operational;
- the last release closes and evicts the runtime;
- reopen after the last close recovers both conversational and episodic state from the same BDR-backed store;
- conflicting native libraries for one active store fail closed;
- all existing Python/native parity tests remain green;
- Android arm64, Ubuntu, Windows and BDR gates remain green.

## Remaining P0 work after this slice

1. Make the native server runtime the production default after the shared-runtime gate is accepted.
2. Remove duplicated authoritative Python ranking/provenance algorithms once native is the production path.
3. Run the #88 benchmark matrix at 100 / 1,000 / 10,000 records: ingest p50/p95, resolve p50/p95, RSS, selected-context size and restart/load time.

Do not close #88 until these production-path and benchmark criteria are satisfied.
