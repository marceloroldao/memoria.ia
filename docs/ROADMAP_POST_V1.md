# Memoria.ia — Post-v1 Evolution Roadmap

Status: planning document for work **after** the v1.0 release gate.

This roadmap is intentionally separated from `docs/ROADMAP_V1.md`. The current v1.0 candidate must remain focused on stabilization, reproducibility and release acceptance. No item below is allowed to expand the v1.0 RC scope unless it fixes a demonstrated release-blocking regression.

## 1. Long-term direction

Memoria.ia should evolve from a persistent retrieval engine into a local-first cognitive memory substrate that can provide:

- persistent state;
- semantic concepts and relations;
- episodic and temporal trajectories;
- memory consolidation and correction;
- minimal-context selection;
- provenance and confidence;
- resolutive inference over stored knowledge;
- multimodal event memory;
- distributed/federated memory boundaries through MA2A.

The target architecture remains:

```text
application / OFF.IA / agent
          ↓
      Memoria.ia
          ├── working memory
          ├── episodic memory
          ├── semantic memory
          ├── relations / provenance
          ├── temporal trajectories
          ├── consolidation
          └── resolutive inference
          ↓
        BDR
   durable persistence
          ↓
optional local LLM
 language / verbalization
```

A local LLM is not the owner of memory. BDR is not the owner of semantics. Memoria.ia remains the authority for memory state, relations, provenance, trajectories and context selection.

## 2. Architectural invariants

All post-v1 work must preserve these invariants:

1. **Local-first:** personal memory must work without cloud access.
2. **Memory authority:** applications must not duplicate Memoria.ia semantics.
3. **Persistence boundary:** BDR owns durable storage; Memoria.ia owns meaning and lifecycle.
4. **LLM neutrality:** local or cloud LLMs are optional consumers; they must not become the authoritative memory store.
5. **Fail closed:** production native paths must not silently fall back to a second authoritative implementation.
6. **Provenance first:** generated answers must not become self-confirming truth without source lineage.
7. **Conservative open-set behavior:** uncertain retrieval should remain `UNRESOLVED` rather than fabricate relevance.
8. **Personal/public separation:** learning from private conversations, images, audio, video or sensors remains local by default. Knowledge intentionally learned from public sources may later be eligible for MA2A/public federation under a separate policy boundary.
9. **Evidence before claims:** every promoted capability needs deterministic tests, negative tests, persistence/restart tests and benchmark evidence where applicable.
10. **No forced neural dependency:** neural models may be adapters or optional helpers, but the memory core must not require them unless a future explicit architecture decision changes this invariant.

## 3. Phase A — v1.x memory consolidation and lifecycle

### Goal

Turn raw learned turns and facts into a stable long-term memory lifecycle.

### Capabilities

- duplicate/redundant memory detection;
- reinforcement of repeated facts without duplicating them;
- correction and supersession chains;
- contradiction handling;
- confidence evolution based on independent evidence;
- active/inactive/superseded memory states;
- configurable retention and deconsolidation policies;
- compact lineage-preserving consolidation.

### Example

```text
old:  car.color = blue
new:  car.color = red
state: current = red
history: blue remains preserved as a superseded past state
```

### Exit criteria

- deterministic consolidation tests;
- correction does not destroy provenance;
- restart preserves consolidated state;
- repeated assistant-generated statements cannot increase authority by self-confirmation;
- measurable reduction in redundant stored memories on long-session workloads.

## 4. Phase B — semantic concept layer

### Goal

Move beyond lexical similarity toward stable concepts and relations.

### Capabilities

- concept identity independent of surface wording;
- synonyms and aliases;
- polysemy / sense separation;
- hierarchical relations;
- typed predicates and properties;
- concept merging and splitting with provenance;
- relation traversal across equivalent terminology.

### Example

```text
charger -> voltage -> 34 V
DDP <-> potential difference <-> voltage
```

A query such as `qual a DDP do meu carregador?` should be able to reach the 34 V fact through concept relations without requiring the exact phrase originally learned.

### Exit criteria

- synonym/paraphrase suites;
- polysemy stress tests;
- ambiguity returns `UNRESOLVED` when multiple senses cannot be distinguished;
- relation traversal does not leak trajectory-local context across sessions;
- no domain-specific hard-coded rules in the core.

## 5. Phase C — layered memory and resolutive time

### Goal

Give different memory classes different update and aging dynamics instead of one uniform lifetime.

### Proposed layers

- working memory;
- active conversation trajectory;
- episodic memory;
- semantic memory;
- procedural memory;
- preferences/habits;
- consolidated long-term memory.

### Resolutive-time hypothesis

Memory update rate should be allowed to depend on density/stability. High-density consolidated knowledge changes more slowly; low-density working context changes quickly.

Conceptually:

```text
higher consolidation/density -> slower update dynamics
lower consolidation/density  -> faster update dynamics
```

This must first be implemented as an experimentally testable scheduling/lifecycle model, not as an unsupported physical claim.

### Exit criteria

- explicit per-layer update policies;
- reproducible temporal tests;
- no accidental loss of high-authority long-term facts;
- corrections can still override old consolidated facts when new authoritative evidence exists;
- benchmark memory churn and update cost.

## 6. Phase D — resolutive inference over memory

### Goal

Allow Memoria.ia to derive conclusions from stored relations before asking an LLM to verbalize them.

### Desired flow

```text
query
  ↓
concept resolution
  ↓
relevant relations
  ↓
resolutive inference
  ↓
conclusion + evidence path + confidence
  ↓
optional LLM verbalization
```

### First scope

- equivalence/substitution;
- typed relation chaining;
- temporal state resolution;
- provenance-preserving multi-hop conclusions;
- contradiction-aware inference;
- bounded inference depth and cost.

### Non-goal

Do not attempt to replace a general-purpose LLM in this phase. The purpose is to make conclusions derivable from explicit memory structure and to reduce how much reasoning/context must be delegated to the model.

### Exit criteria

- every conclusion exposes its evidence path;
- no conclusion can gain more authority than its strongest valid source policy allows;
- cyclic relations do not create infinite inference;
- negative/adversarial tests;
- comparison of LLM-only versus Memoria-assisted context size and correctness on controlled tasks.

## 7. Phase E — autonomous learning and curiosity

### Goal

Let Memoria.ia identify useful knowledge gaps and decide what should be learned, without turning every conversation into permanent truth.

### Capabilities

- classify candidate memories: fact, preference, event, hypothesis, instruction, generated statement;
- importance/novelty estimation;
- detect missing relations or unanswered concepts;
- record curiosity/gap objects;
- optional public-source research adapter;
- source trust and provenance policies.

### Privacy boundary

```text
personal observation / chat / photo / audio / video / sensor
    -> private local memory

intentional public-source research
    -> public-knowledge candidate
    -> future MA2A policy/federation boundary
```

Public and private knowledge must never be merged or exported implicitly.

### Exit criteria

- explicit source class on autonomous memories;
- generated text cannot silently become authoritative fact;
- curiosity queue is bounded and inspectable;
- offline operation remains fully functional;
- public federation remains opt-in and outside the personal-memory path.

## 8. Phase F — multimodal event memory

### Goal

Represent observations from multiple sensor modalities as events and relations rather than treating text as the only memory source.

### Candidate modalities

- image;
- audio;
- video;
- location;
- temperature;
- device/IoT sensors;
- robotics state and actions.

### Boundary

Perception modules may use conventional or Resolutive technologies, but Memoria.ia receives normalized events/concepts/relations. Large raw media objects should not automatically become the semantic memory representation.

### Exit criteria

- common event schema across modalities;
- temporal ordering and source provenance;
- cross-modal relation tests;
- configurable retention of raw media versus derived memory;
- mobile/embedded resource budgets measured.

## 9. Phase G — semantic compression and large-scale memory

### Goal

Prevent lifetime memory from growing as an unbounded transcript archive.

### Capabilities

- concept-level deduplication;
- episodic summarization with reversible provenance links;
- consolidation of repeated relations;
- cold/archival memory tiers;
- incremental indexes;
- bounded active working set;
- compaction without losing correction history.

### Benchmarks

At minimum measure:

- 10k, 100k and 1M memory objects where feasible;
- ingest p50/p95;
- resolve p50/p95;
- restart/load time;
- disk bytes per useful fact/relation;
- active RAM;
- selected-context size;
- correctness before/after compaction.

Do not claim general O(1) semantic resolution unless the complete semantic path actually demonstrates it.

## 10. Phase H — distributed memory / MA2A boundary

### Goal

Allow multiple Memoria.ia instances to cooperate without turning personal memory into a centralized data pool.

### Proposed hierarchy

```text
personal Memoria.ia
       ↓
device / local domain memory
       ↓
private MA2A
       ↓
federated MA2A
       ↓
public knowledge / resolutive services
```

### Required controls

- cryptographic identity;
- explicit scopes;
- local/private/shared/public classes;
- provenance preserved across nodes;
- conflict resolution;
- revocation and deletion propagation where policy requires;
- no raw private-memory broadcast by default.

The MA2A protocol itself remains a separate project/boundary. Memoria.ia should expose only the interfaces necessary to participate safely.

## 11. Suggested execution order

The default sequence after v1.0 is:

```text
v1.0 stable
   ↓
A. consolidation/lifecycle
   ↓
B. semantic concepts/polysemy
   ↓
C. layered memory + resolutive time
   ↓
D. resolutive inference
   ↓
E. autonomous learning/curiosity
   ↓
F. multimodal event memory
   ↓
G. semantic compression/scaling
   ↓
H. MA2A distributed boundary
```

Phases may overlap experimentally, but promotion into the stable core must follow evidence and compatibility gates.

## 12. Versioning guidance

Do not bind the roadmap to arbitrary version numbers too early. Use feature branches and evidence gates first. A possible mapping is:

- v1.1.x — consolidation/lifecycle;
- v1.2.x — concept/semantic layer;
- v1.3.x — layered temporal memory;
- v1.4.x — resolutive inference;
- v1.5.x — autonomous learning/curiosity;
- v1.6.x — multimodal events;
- v1.7.x — compression/scaling;
- v2.0 — only when a major compatibility or distributed-memory contract justifies it.

The mapping is advisory; test evidence decides promotion.

## 13. Immediate rule after v1.0

The first post-v1 development cycle should **not** start by adding MA2A, multimodality or a new neural layer. Start with consolidation and semantic concept identity because these capabilities strengthen every later layer while preserving the already validated OFF.IA -> Memoria.ia -> BDR architecture.

## 14. Product-level objective

The long-term product goal is that an application may replace or upgrade its language model without losing accumulated experience:

```text
model A -> model B
          ↑
  same Memoria.ia state
```

The durable identity of accumulated experience should live primarily in Memoria.ia/BDR, not inside a specific LLM's weights.
