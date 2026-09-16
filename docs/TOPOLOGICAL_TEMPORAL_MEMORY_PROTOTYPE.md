# Experimental topological + temporal memory prototype

Status: **isolated experiment; not part of the frozen RC7 runtime**.

Branch: `experiment/topological-temporal-memory-v1`

Baseline used to create the branch: `f64c1bc8837a7d44815674f7b850bd71803ee9be` (`main`, RC7 publication lineage).

Historical baseline that must remain reproducible: `v1.0.0-rc5` / Native Relational Memory Candidate.

Architectural direction source: `docs/POST_V1_NODE_ONTOGENESIS_AND_BRANCHING.md`, including commit `7422bdb558b8799fb439cd7d8abcf5fc8e0b7103`.

## Why this is a sidecar

The existing runtime already contains useful pieces that should be reused rather than rewritten:

- `EvidenceCore` stores source-backed subject/predicate/object relations, evidence IDs, namespace, epoch, provenance, origin and confidence;
- `EvidenceCore.evidence_history()` preserves historical observations while `active_edges()` projects the currently active relation set;
- bounded relational activation already traverses persisted graph structure without requiring embeddings or an LLM;
- the product/native/mobile layers have validated ABI, persistence and provenance barriers that must not be disturbed by the first ontogenesis experiment.

The first prototype therefore does **not** replace EvidenceCore, BDR storage, the mobile ABI, conversation APIs or semantic activation. It validates the missing primitives separately.

## Added experimental primitives

`src/memoria_resolutiva/topological_memory.py` introduces:

1. `AddressSpace`
   - deterministic node addresses from `kind + canonical_value`;
   - symbol, prefix-fragment, word, phrase and text nodes;
   - explicit composition edges;
   - reuse of stable addresses across repeated ingestions;
   - exact raw-input preservation through a separate provenance address;
   - initial reuse/branching metrics.

2. `TemporalEventStore`
   - monotonic internal sequence counter per occurrence/event;
   - reusable entity, attribute and value addresses;
   - append-only state observations;
   - explicit transitions only when the value changes;
   - separation between sequence, optional `event_time`, and UTC ingestion time.

3. `TemporalOperator`
   - `CURRENT`;
   - `PREVIOUS_STATE`;
   - `FIRST_STATE`;
   - `EXISTED_IN_HISTORY`;
   - `STATE_BEFORE_VALUE`;
   - `STATE_AFTER_VALUE`;
   - `STATE_DIFF`;
   - `HISTORY`.

4. `CognitiveResult`
   - structural result returned before any language/verbalization layer.

## Current test matrix

`tests/test_topological_memory_prototype.py` covers:

### Phase A — addressing

- repeated `acordei` reuses the same word address;
- case changes do not create a second canonical word address;
- lower symbol composition for `hoje` is inspectable;
- prefix fragments such as `ho` and `hoj` are addressable;
- original raw strings remain exactly reconstructable;
- duplicate-address count remains zero by construction.

### Phase B — sequential events

- explicit example sequences `12`, `24`, `31` are preserved;
- sequence belongs to events, not to reusable value nodes;
- backward sequence insertion is rejected by the prototype contract.

### Phase C — transitions

- `azul -> preta -> branca` yields two transitions;
- all three historical states remain accessible.

### Phase D — temporal resolution primitive

The deterministic resolver is tested for all eight initial temporal operators at the structural API level.

Natural-language parsing of questions such as `Qual era a cor da minha camisa?` is deliberately not coupled into this first core slice. The next slice should translate language into the generic tuple:

```text
ENTITY + ATTRIBUTE + optional VALUE + TEMPORAL_OPERATOR
```

without domain-specific rules for `camisa`.

### Phase E — domain independence

The same resolver is exercised with:

- car/color;
- sensor/temperature;
- server/IP;
- robot/position;
- cat/name.

No domain-specific resolver branch is present.

## Reuse vs new components

### Reuse later

- `EvidenceCore` provenance/confidence/origin model;
- namespace isolation;
- existing bounded graph activation;
- persistence adapters and BDR after the in-memory semantics are stable;
- existing context compiler / semantic activation boundary as consumer of compact cognitive results.

### New primitives that were missing

- deterministic reusable address space below entity/relation scale;
- explicit composition topology across symbolic layers;
- first-class event sequence independent of node identity;
- first-class transitions;
- generic temporal operator resolver returning a cognitive result.

## Known limitations / negative findings

These are intentional and must not be hidden:

1. The prototype is currently in-memory only; restart persistence has not yet been proven.
2. Addressing uses deterministic BLAKE2b identifiers for the experiment; this is not yet a decision about the eventual BDR/native address format.
3. Prefix fragments are an intentionally bounded first representation. Arbitrary substrings/morphemes are not materialized.
4. Lemma/concept identity (`acordei -> acordar -> ACORDAR`) is not yet implemented; only normalized surface-word reuse is proven in the first slice.
5. Natural-language query parsing is not yet connected to the temporal resolver.
6. Density is exposed as graph degree, but selectivity/ranking is not assigned a formula yet. The specification explicitly requires benchmarking before choosing one.
7. No migration path from existing EvidenceCore epochs to sequence events has been committed yet.
8. No BDR schema or mobile ABI changes have been made.
9. No claim is made yet about memory-growth advantage versus the frozen engine; benchmarks must measure this.

## CI validation note

Issue #277 identified that the experimental PR workflow filtered the PR base branch as `experiment/**`, so experiment heads targeting `main` never ran the intended Ubuntu/Windows regression. PR #278 corrected the workflow trigger on `main` without runtime changes. This experiment must not be considered regression-validated until a new PR synchronization event produces successful checks on the experimental head.

## Next implementation sequence

1. Run the new tests together with the complete existing suite and record regressions.
2. Add a generic query-intent adapter that emits structural temporal operators without domain hardcoding.
3. Add benchmark instrumentation for node reuse, new-node growth, branching density, hub behavior, temporal accuracy and latency.
4. Stress repeated high-frequency tokens (`de`, `para`, `que`, `e`, `a`, `o`) and measure density/selectivity candidates without locking a formula.
5. Add persistence behind a new additive adapter; compare SQLite/current store/BDR rather than modifying the frozen storage path.
6. Map trustworthy EvidenceCore relations into temporal events experimentally, preserving provenance authority and contamination barriers.
7. Feed compact `CognitiveResult` objects into the Context Compiler path.
8. Only after restart, scale and regression evidence should the project decide whether this sidecar converges with the stable engine.

## Freeze gate for a future integrated candidate

Do not propose an OFF.IA-integrated freeze until at least:

- full baseline suite passes unchanged;
- deterministic natural-language acceptance cases pass;
- restart/persistence equivalence passes;
- hub-density stress test passes without activation explosion;
- generalization matrix passes without entity-specific rules;
- measured memory growth and retrieval latency are recorded;
- provenance/LLM contamination regressions remain green.
