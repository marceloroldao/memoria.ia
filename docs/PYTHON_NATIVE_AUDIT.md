# Python ↔ Native Authority Audit

Status: active P0 migration tracker for Issue #88.

## Objective

Converge Android, Windows, Linux and PC/server on one authoritative Memoria.ia native runtime while keeping Python for FastAPI, Pydantic, provider adapters, administration, tests and orchestration.

The migration rule is: **one authoritative semantic implementation, multiple thin product boundaries**.

## Current authority map

| Capability | Authoritative/current native path | Python role / remaining work |
| --- | --- | --- |
| Semantic candidate ranking + confidence | `native/mobile/semantic_kernel.c` | Legacy Python reference remains only for parity tests until final duplicate-removal slice |
| Relation extraction | `native/mobile/relation_extractor.c` | Legacy Python parser remains only as a parity/reference implementation |
| Trajectory/window resolve | `native/mobile/trajectory_*` | Python retains tests/orchestration |
| Temporal previous/current | `native/mobile/temporal_state_*` | Production conversation route delegates to native runtime |
| Episodic recall | `native/mobile/episodic_kernel.c` | Legacy Python episodic service remains available only through explicit Python runtime mode |
| Turn persistence | `native/mobile/mobile_persistence_bdr.c` | BDR is authoritative persistence for native runtime |
| Persistent namespaces | native turn `namespace` | Server maps product `session_id` to namespace; OFF.IA omits namespace and retains global personal memory |
| Correction/supersession | native learn/persistence boundary | Legacy Python implementation remains only for reference/parity until removal |
| Provenance/authority lineage | native parent/root lineage + supersession metadata | Python `memory_provenance.py` is no longer the production conversation authority once native default is accepted |
| Relation identity | persisted native relation memory IDs | Thin server adapter pre-computes bounded deterministic IDs; native extraction decides how many are consumed |
| Native process ownership | `native_runtime.py` shared DLL/handle/lock manager | Python owns lifecycle only; semantic state remains inside one native runtime/store |
| Episodic server adapter | `NativeEpisodicService` | FastAPI/Pydantic remain Python |
| Conversation server adapter | `NativeConversationService` | FastAPI/Pydantic/auth remain Python; semantic work is native |

## Product boundaries

### OFF.IA

`OFF.IA -> Memoria.ia native/mobile ABI -> Resolutive-DB`

OFF.IA must not parse BDR, duplicate semantic rules, or use product-server namespaces for its persistent personal memory. Its `session_id` continues to describe the active conversation window/trajectory.

### PC/server

`FastAPI/Pydantic -> thin native adapter -> shared native runtime -> Memoria.ia native core -> Resolutive-DB`

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
- shared server native runtime manager with one DLL/handle/lock, reference-counted leases and joint conversation/episodic restart recovery.

## Current slice — native server production default

The production server must no longer reach the legacy Python semantic implementation merely because runtime configuration was omitted.

Frozen decisions:

- `MEMORIA_CONVERSATION_RUNTIME` defaults to `native`;
- `MEMORIA_EPISODIC_RUNTIME` defaults to `native`;
- missing `MEMORIA_NATIVE_LIB` in default/native mode is a startup error; there is no fallback to Python;
- the legacy Python paths remain available only when operators explicitly set the relevant runtime variable to `python`;
- the production Docker image builds `libmemoria_mobile.so` from this repository plus Resolutive-DB pinned at `1f6b7ccbe16bdfed2f1b5dcebceb17887bf6916e`;
- the image embeds the native library, sets the native runtime environment explicitly, verifies mobile ABI v1 during image build and keeps BDR-backed state under `/data`;
- `.env.example` exposes the migration explicitly, including how source/local deployments must point `MEMORIA_NATIVE_LIB` at a platform-native build;
- when both production capabilities are native they share the unified `native-runtime` store introduced in the previous slice.

Acceptance requirements:

- a clean server process with no conversation/episodic runtime overrides selects native for both capabilities;
- an explicit `python`/`python` configuration remains usable as a reference/test path without a native library;
- a clean default/native process without `MEMORIA_NATIVE_LIB` fails during startup;
- the production Docker image contains a loadable ABI-v1 `libmemoria_mobile.so` built against the exact pinned BDR revision;
- the image starts with native defaults and reports native conversation + episodic runtime in `/api/v1/storage/health`;
- conversation ingest/resolve and episodic store/recall work in the production image;
- a container restart preserves both capabilities through the shared BDR-backed native store;
- existing Python/native parity, Android arm64, Ubuntu, Windows and BDR gates remain green.

## Remaining P0 work after this slice

1. Remove or isolate duplicated authoritative Python ranking/relation/provenance logic so it cannot be confused with the production implementation; retain only reference fixtures/helpers that are still useful for parity.
2. Run and record the #88 benchmark matrix at 100 / 1,000 / 10,000 records: ingest p50/p95, resolve p50/p95, RSS, selected-context size and restart/load time.

Do not close #88 until duplicate-authority cleanup and benchmark evidence are complete.
