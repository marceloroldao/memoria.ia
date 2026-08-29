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
- native server production default with fail-closed library requirement and a Docker image that proves native conversation/episodic persistence across restart;
- Python reference semantics isolated from native production startup; explicit Python mode remains parity/reference only.

## Current slice — native benchmark matrix

The final P0 gate measures the accepted native production path at 100 / 1,000 / 10,000 conversational memories. The harness records ingest p50/p95, resolve p50/p95, RSS, selected-context bytes, restart/load time, first resolve after restart and durable store size. Semantic correctness remains a hard gate; there is no encoded performance threshold or superiority claim.

The first matrix run exposed a real pre-benchmark limitation rather than a measurement problem: the mobile/server native handle still used a fixed `MAX_TURNS=256` array and returned `MEMORIA_MOBILE_UNRESOLVED` when the 1,000-record run crossed that limit. The 100-record run passed; the 1,000-record run stopped at the legacy capacity; 10,000 was therefore not measured.

This limitation is being removed structurally rather than by increasing a constant:

- native turn rows now grow geometrically from an initial 256-slot allocation;
- persisted stores with more than 256 turns can be reopened and loaded;
- the semantic-source scratch buffer grows with the active turn count instead of using a fixed stack array;
- dynamic allocations are released by `memoria_mobile_close`;
- a dedicated C regression writes 300 turns, closes, reopens through BDR and resolves the final turn, proving operation above the former ceiling.

The fixed 256-episode limit is intentionally unchanged in this slice because the benchmark evidence identified the conversation-turn capacity specifically; unrelated limits are not broadened without a separate requirement/evidence gate.

## Remaining P0 acceptance

Run and version the successful #88 benchmark matrix at 100 / 1,000 / 10,000 records with:

- ingest p50/p95;
- resolve p50/p95;
- RSS;
- selected-context size;
- restart/load time;
- raw JSON evidence tied to exact commit and GitHub Actions run.

If the dynamic-capacity regression, normal candidate gates and complete benchmark matrix are accepted, Issue #88 can be closed.
