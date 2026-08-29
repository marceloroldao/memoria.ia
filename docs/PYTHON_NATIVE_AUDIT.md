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
| Episodic server adapter | `NativeEpisodicService` | FastAPI/Pydantic remain Python |
| Conversation server adapter | `NativeConversationService` | FastAPI/Pydantic/auth remain Python; runtime is opt-in while response metadata is frozen |

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
- native parent lineage, authority clamping and superseded-by metadata;
- opt-in native conversation HTTP adapter;
- shared product relation extraction parity for compact Portuguese copulas, elliptic relations, dedupe and noise filtering;
- deliberate native English `is` compound-subject compatibility preserved for mobile/temporal entities.

## Current slice — confidence and response metadata parity

The selected memory already has semantic parity. This slice freezes the remaining public response contract before native conversation can become the default server path.

Frozen decisions:

- native semantic confidence is the v1 authority; it combines normalized lexical overlap with source authority and is capped by the native kernel contract;
- public confidence is serialized/normalized to six decimal places, matching the native ABI JSON precision and avoiding language-specific floating-point artifacts;
- the legacy Python conversation service keeps its selection logic unchanged and temporarily mirrors only the native public confidence formula for parity; this reference path is removed after native becomes production default;
- the thin `NativeConversationService` does not recompute ranking or confidence;
- public relation `epoch` means persistent conversational `created_order`, not the internal `EvidenceCore` sequence;
- native resolve provenance exposes persisted `created_order` and `created_time`; the adapter copies those durable fields into the public response.

Acceptance requirements:

- compare complete supported ingest/resolve JSON between Python and native paths;
- preserve relation IDs, namespace, source authority, immediate source type, parent lineage, ultimate source, created order/time and supersession metadata;
- preserve correction and turn-fallback behavior;
- unresolved responses remain identical;
- restart preserves the same public response;
- Android arm64, Ubuntu, Windows and BDR gates remain green.

## Remaining P0 work after this slice

1. Consolidate native episodic and conversation handles behind a shared runtime manager so one process does not maintain unnecessary duplicate native stores.
2. Make the native server runtime the production default only after the frozen response contract is accepted.
3. Remove duplicated authoritative Python ranking/provenance algorithms once native is the production path.
4. Run the #88 benchmark matrix at 100 / 1,000 / 10,000 records: ingest p50/p95, resolve p50/p95, RSS, selected-context size and restart/load time.

Do not close #88 until these production-path and benchmark criteria are satisfied.
