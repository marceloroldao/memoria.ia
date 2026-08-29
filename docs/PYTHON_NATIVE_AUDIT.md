# Python -> Native Core Audit

Status: implementation planning snapshot
Baseline: `integration/v1.0-candidate` at `06454c1ac22b698370a68f5d64c6edf06a637460`

## Objective

Reduce latency, memory overhead and behavioral divergence by moving only runtime-critical Memoria.ia algorithms from Python into the shared native C/C++ core. Python remains the orchestration and product layer where interpreter overhead is not on the hot path.

This is not a rewrite mandate. The migration rule is:

> migrate hot-path algorithms and duplicated semantics; keep orchestration, HTTP, experiments, tests and benchmarks in Python unless profiling proves otherwise.

The target architecture is:

```text
HTTP / CLI / applications (Python, Kotlin, other hosts)
                  |
                  v
        thin language adapter
                  |
                  v
       Memoria.ia Native Core
    C ABI + optional C++ internals
      | semantic / relations
      | provenance / authority
      | trajectory / temporal state
      | episodic recall
      | evidence graph / ranking
      v
          Resolutive-DB / BDR
```

Android and PC/server must converge on the same native semantics. Python must not remain a second independent implementation of recall/ranking once native parity exists.

## What is already native

The Android/mobile path already contains native implementations for important runtime work:

- `native/mobile/semantic_kernel.c`
- `native/mobile/trajectory_kernel.c`
- `native/mobile/trajectory_json_adapter.c`
- `native/mobile/episodic_kernel.c`
- `native/mobile/temporal_state_kernel.c`
- `native/mobile/temporal_state_relation_adapter.c`
- `native/mobile/relation_extractor.c`
- `native/mobile/relation_adapter.c`
- `native/mobile/mobile_persistence_bdr.c`
- `native/mobile/memoria_mobile.c`
- BDR native integration and `native/bdr_atomic_pybind.cpp`

These should evolve from a mobile-only implementation into the shared native core rather than being reimplemented again for server use.

## Python classification

### P0 - migrate/unify first

These modules contain runtime semantics or loops that duplicate capabilities already becoming native. They are the highest-value migration targets.

#### `src/memoria_resolutiva/product_conversation.py`

Current responsibilities include:

- tokenization and query normalization;
- natural-language relation extraction via regex;
- semantic overlap scoring;
- ambiguity detection;
- source-authority selection;
- conversation ingest/resolve behavior;
- FastAPI/Pydantic endpoint glue.

Decision:

- **move semantic/relation/ranking logic to native**;
- **keep FastAPI/Pydantic request/response glue in Python**;
- Python should call one native ingest/resolve contract instead of implementing a second resolver.

Reason: this is direct duplication of the Android C path and is therefore both a performance and correctness/parity risk.

#### `src/memoria_resolutiva/evidence_core.py`

Current responsibilities include:

- in-memory evidence edge storage;
- active-edge selection;
- conflict detection;
- graph adjacency construction;
- conservative BFS/path inference;
- confidence/origin/reliability filtering.

Decision: **native core candidate P0**.

Reason: graph traversal and repeated grouping/scanning are hot-path operations as memory volume grows. This module also defines central semantics, so keeping a separate Python graph would create server/mobile divergence.

Native target should preserve explicit evidence only; no natural-language parsing belongs inside the graph kernel.

#### `src/memoria_resolutiva/memory_provenance.py`

Current responsibilities include:

- source-type authority;
- parent lineage;
- supersession;
- ultimate-source traversal;
- lineage deduplication;
- authoritative candidate selection.

Decision: **native core candidate P0**.

Reason: provenance is already required by mobile semantic selection. One native provenance implementation should be used by all hosts so generated echoes cannot receive different authority on Android versus server.

#### `src/memoria_resolutiva/episodic_recall.py`

Decision: **replace runtime implementation with the shared native episodic kernel after parity tests**.

#### `src/memoria_resolutiva/temporal_memory.py`

Decision: **replace runtime state/ordering resolution with the shared native temporal state kernel after #85 is complete**.

#### `src/memoria_resolutiva/product_evidence.py`

Decision: inspect each method, then move evidence/ranking/traversal operations into native while retaining product/service orchestration in Python.

### P1 - migrate only after P0 parity and profiling

Likely runtime modules that may benefit from native implementation but should not be rewritten before measurements:

- core route/index operations behind `api_v90.py` where they remain Python-only;
- lifecycle/reinforcement/challenge loops used per request;
- source-reliability calculations if profiling shows repeated Python iteration;
- high-volume indexing, compaction and batch transformations;
- Python persistence adapters still performing record-by-record work that BDR can own natively.

For each P1 candidate, require a benchmark demonstrating material latency, RSS or throughput benefit before migration.

### Keep in Python - orchestration/product boundary

These are not primary migration targets merely because they are Python:

- FastAPI HTTP routing and Pydantic schemas;
- `product_server.py` / `product_http.py` style server bootstrap;
- cloud LLM adapters (`openai_adapter.py`, `gemini_adapter.py` and equivalents);
- license/admin/configuration flows;
- backup/export coordination where BDR/native I/O is already doing the heavy work;
- application-specific integration glue.

`product_service.py` is a mixed case. Its product facade, organization scoping and manifest coordination can remain Python. Memory-engine operations underneath it should call the native core. File-format compatibility must be preserved during any migration.

### Keep in Python - research and validation

Do not port these for speed unless a concrete runtime dependency appears:

- `benchmarks/*.py`;
- `experiments/*.py`;
- `tests/*.py`;
- release/validation scripts;
- data generation and analysis scripts.

Python is preferable here because iteration speed, inspection and reproducibility matter more than request latency.

### Legacy/duplicate candidates

After native parity is proven, Python implementations that duplicate native semantics should be marked deprecated, then removed only after:

1. server paths use the native implementation;
2. parity fixtures pass;
3. snapshot/restart compatibility is demonstrated;
4. no supported import/API still relies on the old class;
5. one release cycle documents the deprecation.

Do not delete historical experimental code merely to reduce the Python percentage of the repository.

## Migration sequence

### Phase N0 - measurement and parity harness

Before replacing server semantics, create a cross-runtime corpus that sends identical operations to Python and native implementations and compares normalized results.

Required cases:

- factual ingest and exact recall;
- semantic/relational recall;
- question versus assertion;
- provenance and generated echo suppression;
- corrections/supersession;
- trajectory and session isolation;
- episodic latest/ordered recall;
- temporal previous/current state;
- ambiguity -> UNRESOLVED;
- restart through BDR.

Measure at 100, 1,000 and 10,000 stored records:

- ingest p50/p95;
- resolve p50/p95;
- selected-context size;
- process RSS;
- allocations if available;
- restart/load time;
- result parity.

### Phase N1 - native conversation semantic contract

Promote the mobile-native semantic/relation/trajectory functions into a host-neutral library boundary. Keep `memoria_mobile_*` as a compatibility wrapper, not as the canonical home of the algorithms.

Candidate naming:

```text
native/core/
  memoria_core.h
  evidence_core.*
  provenance_core.*
  relation_core.*
  semantic_core.*
  trajectory_core.*
  episodic_core.*
  temporal_state_core.*
```

The exact directory/name may change, but there must be one implementation shared by Android, Windows and Linux.

### Phase N2 - native evidence + provenance

Port `EvidenceCore` and `MemoryProvenanceIndex` semantics behind a stable C ABI. C++ internals are acceptable where containers materially simplify graph/index work, provided the public ABI remains C-compatible.

Important: C++ is preferred over forcing complex graph containers into hand-written C when it improves safety and maintainability. The goal is native shared runtime, not C for ideological reasons.

### Phase N3 - Python becomes a thin adapter

Refactor `product_conversation.py` so Python owns:

- authentication/API schema;
- conversion between Python models and ABI payloads;
- HTTP error mapping.

It must no longer own the authoritative scoring/ranking/provenance algorithm.

### Phase N4 - deprecate duplicated server algorithms

Once native parity and benchmarks pass, deprecate independent Python hot-path implementations and document the native core as the source of truth.

## Acceptance criteria for a migration

A Python hot-path component is considered successfully migrated only when:

- output parity exists for the agreed corpus;
- Android + Ubuntu + Windows gates pass;
- BDR restart/persistence parity passes;
- no hard-coded domain examples were added;
- public supported API remains compatible or has an explicit versioned migration;
- native latency is measured rather than assumed;
- native RSS/throughput are recorded;
- Python fallback is not silently used in production paths after native promotion.

## Performance expectations

Native code is expected to help most where Python currently performs repeated loops, grouping, graph traversal, ranking or record conversions. It will not automatically make HTTP/network/LLM latency faster.

For OFF.IA, llama.cpp inference will usually remain the largest latency component. The purpose of this migration is therefore not only raw speed: it also reduces memory overhead, makes large memory sets scale better, and ensures one deterministic memory behavior across Android/PC/server.

## Immediate recommendation

Start with **native evidence + provenance parity**, not with HTTP code. `product_conversation.py` should then be converted into a thin adapter over that shared core.

Do not migrate benchmarks, experiments or FastAPI merely to increase the amount of C/C++ in the repository.
