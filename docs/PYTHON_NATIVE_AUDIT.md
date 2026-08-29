# Python ↔ Native Authority Audit

Status: active P0 migration tracker for Issue #88.

## Objective

Converge Android, Windows, Linux and PC/server on one authoritative Memoria.ia native runtime while keeping Python for FastAPI, Pydantic, provider adapters, administration, tests and orchestration.

The migration rule is: **one authoritative semantic implementation, multiple thin product boundaries**.

## Current authority map

| Capability | Authoritative/current native path | Python role / remaining work |
| --- | --- | --- |
| Semantic candidate ranking | `native/mobile/semantic_kernel.c` | Python parity/reference code remains until server migration completes |
| Relation extraction | `native/mobile/relation_extractor.c` | `product_conversation.py` parser remains the production default until native conversation runtime is accepted |
| Trajectory/window resolve | `native/mobile/trajectory_*` | Python retains tests/orchestration |
| Temporal previous/current | `native/mobile/temporal_state_*` | Server exposure is being routed through native conversation runtime |
| Episodic recall | `native/mobile/episodic_kernel.c` | `NativeEpisodicService` is opt-in; Python remains default during migration |
| Turn persistence | `native/mobile/mobile_persistence_bdr.c` | BDR is authoritative persistence for native runtime |
| Persistent namespaces | native turn `namespace` | Server maps product `session_id` to namespace; OFF.IA omits namespace and retains global personal memory |
| Correction/supersession | native learn/persistence boundary | Python implementation remains until production conversation route switches |
| Provenance/authority lineage | native parent/root lineage + supersession metadata | Python `memory_provenance.py` remains a reference/legacy server path during migration |
| Relation identity | persisted native relation memory IDs | Server may pre-compute bounded deterministic IDs; native extraction decides how many are consumed |
| Episodic server adapter | `NativeEpisodicService` | FastAPI/Pydantic remain Python |
| Conversation server adapter | `NativeConversationService` (PR #103 candidate) | FastAPI/Pydantic/auth remain Python; runtime remains opt-in until gates/parity pass |

## Product boundaries

### OFF.IA

`OFF.IA -> Memoria.ia native/mobile ABI -> Resolutive-DB`

OFF.IA must not parse BDR, duplicate semantic rules, or use product-server namespaces for its persistent personal memory. Its `session_id` continues to describe the active conversation window/trajectory.

### PC/server

`FastAPI/Pydantic -> thin native adapter -> Memoria.ia native core -> Resolutive-DB`

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
- native parent lineage, authority clamping and superseded-by metadata.

## Current slice — native conversation server adapter

Acceptance requirements:

- Python remains the default runtime;
- native mode is explicitly selected with `MEMORIA_CONVERSATION_RUNTIME=native`;
- no Python semantic fallback occurs in native mode;
- deterministic public turn/relation IDs survive migration;
- session namespaces do not leak;
- correction/supersession and generated-parent lineage survive restart;
- unknown/ambiguous queries abstain;
- temporal previous/current is available through the same conversation endpoint;
- Android arm64, Ubuntu, Windows and BDR gates remain green.

## Remaining P0 work after conversation adapter

1. Expand native relation extraction parity for richer/elliptic natural-language relations still handled by `product_conversation.py`.
2. Decide and freeze cross-runtime confidence/response metadata semantics before making native conversation the default server path.
3. Consolidate native episodic and conversation handles behind a shared runtime manager so one process does not maintain unnecessary duplicate native stores.
4. Remove duplicated authoritative Python ranking/provenance algorithms once the native server path becomes production default.
5. Run the #88 benchmark matrix at 100 / 1,000 / 10,000 records: ingest p50/p95, resolve p50/p95, RSS, selected-context size and restart/load time.

Do not close #88 until these production-path and benchmark criteria are satisfied.
