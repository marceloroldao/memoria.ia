# Python ↔ Native Authority Audit

Status: active P0 migration tracker for Issue #88.

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
- native server production default with fail-closed library requirement and a Docker image that proves native conversation/episodic persistence across restart.

## Current slice — isolate Python reference semantics

The production server must not merely prefer the native implementation; it must also avoid loading a second semantic authority into the process when native mode is active.

Frozen decisions:

- `conversation_contract.py` owns conversation DTOs and route attachment without importing ranking, relation extraction or provenance algorithms;
- `episodic_contract.py` owns episodic DTOs and route attachment without importing episodic selection algorithms;
- `NativeConversationService` and `NativeEpisodicService` depend only on those neutral contracts plus the native runtime manager;
- `product_server.py` imports the neutral contracts at startup and lazy-loads Python semantics only inside explicit `runtime=python` branches;
- `reference_conversation.py` and `reference_episodic.py` make the status of the old Python implementations explicit: they are parity/reference paths, not production authority;
- compatibility modules remain available during v1 migration so existing tests and downstream imports are not broken unnecessarily;
- native production startup is gated to prove that `product_conversation`, `product_episodic`, `reference_conversation`, `reference_episodic` and `memory_provenance` are absent from `sys.modules`;
- explicit Python reference mode is separately gated to prove that those reference modules are loaded only when deliberately requested.

Acceptance requirements:

- default/native server startup does not import any reference conversation/episodic semantic module;
- explicit `python`/`python` mode still starts and loads the reference implementations;
- existing HTTP response contracts remain unchanged;
- all prior Python/native parity fixtures remain green;
- Android arm64, Ubuntu, Windows, production container and BDR gates remain green.

## Remaining P0 work after this slice

Run and record the #88 benchmark matrix at 100 / 1,000 / 10,000 records:

- ingest p50/p95;
- resolve p50/p95;
- RSS;
- selected-context size;
- restart/load time.

If the isolation gate and benchmark matrix are both accepted, Issue #88 can be closed.
