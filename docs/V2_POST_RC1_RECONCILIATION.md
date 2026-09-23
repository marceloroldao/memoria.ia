# Memoria.ia V2 — Post-RC1 Reconciliation and Inference Plan

Status: active post-RC1 execution plan  
Frozen baseline: `v2.0.0-rc1`  
Functional freeze: `bd33b9cfcfa78f0e3850fb5e298cbf4cbdc360b9`  
Archived DOI: `10.5281/zenodo.22908785`  
Reconciliation starts from current `main`, without changing the frozen tag.

## Why this reconciliation exists

The V2 line evolved in two partially divergent directions before RC1:

1. the line that reached `main` and was frozen as RC1:
   raw StructuralEvent intake, non-semantic associations, recurrence, time/decay,
   durable recovery, structural text recall and native/mobile structural ABI;

2. an older experimental line that accumulated valuable cognitive mechanisms:
   address trajectories, hierarchical composition, multiscale convergence,
   frontier/branching/rollout/recovery, temporal state, structural equivalence,
   Context Compiler, Response Validator, Learning Gate and cognitive mobile ABI.

The second line is not safe to merge wholesale. Its main Address-Trajectory branch
diverged substantially from RC1 and also contains policies that no longer match the
current architectural direction.

The rule is therefore:

> recover mechanisms, invariants and tests; do not recover obsolete assumptions.

## Reconciliation policy

Every historical capability is classified as one of:

- **RECOVER** — valuable mechanism compatible with current direction;
- **ADAPT** — valuable idea, but implementation/policy must change;
- **TEST-ONLY** — keep the regression/fixture, not the old solution;
- **ABSORBED** — capability already exists in RC1 through a newer implementation;
- **DEFER** — valuable but depends on a later cognitive substrate;
- **DROP** — contradicts current architecture or is superseded.

## Inventory

| Historical line | Classification | Reintegrated role |
| --- | --- | --- |
| Address-Trajectory V2 | RECOVER | modality-neutral trajectory substrate over current opaque structural IDs |
| Hierarchical composition | RECOVER | recurrent structural compositions without semantic labels |
| Multiscale resolver | RECOVER | convergence over atomic + composed trajectory scales |
| Frontier / branching | RECOVER | expose competing structural continuations |
| Multi-step rollout | RECOVER | follow occurrence-local futures without global-address jumps |
| Exhaustion recovery | RECOVER | fresh retrieval after active branches fail; never stitch through a hub |
| Structural equivalence | ADAPT | revocable equivalence from independent recurrent convergence |
| Topological temporal state | ADAPT | stable addresses + versioned evolving state/current/history |
| Structural temporal observation/recall | RECOVER | modality-neutral before/after/simultaneous evidence with provenance |
| Cognitive cycle V2 | DEFER | prediction -> observation -> correction -> recovery after state/attractor gates |
| Active causal loop | DEFER | world intervention only after passive inference is validated |
| Context Compiler | ADAPT | compile addresses/state/trajectories/attractors, not rigid subject/predicate/value facts |
| Response Validator | ADAPT | preserve LLM claims as quarantined evidence; compare against resolved cognitive state |
| Learning Gate | ADAPT | preserve immutable candidate + audit, but remove rigid source==truth policy |
| Mobile cognitive packet ABI | ADAPT | reintroduce only after new cognitive packet schema is frozen |
| Naming/restart/collection fixes | TEST-ONLY | fixtures become adversarial tests; do not port phrase-specific extraction rules |
| Native zero-LLM E2E #317 | TEST-ONLY | preserve no-external-call acceptance goal; do not port stopword/lexical intent rules |
| BDR address-trajectory validation | ADAPT | reuse persistence/crash/reopen gates against current BDR contract |
| Structural observation journal #320 | ABSORBED | superseded by current StructuralObservation pipeline |
| shared BDR handle / dynamic episodic capacity | ABSORBED | already integrated into the modern line |
| current continuous structural association field | ABSORBED/FOUNDATION | becomes one input to later attractor dynamics |
| rigid semantic predicate extraction | DROP | conflicts with non-rigid structural inference goal |
| source class as automatic truth | DROP | provenance is evidence metadata, not truth by itself |
| query-driven learning | DROP | all inference queries remain read-only |

## Phase R0 — Reconciliation baseline

Deliverables:

- this inventory;
- preserve RC1 tag and DOI untouched;
- identify historical tests that remain scientifically useful;
- add one clean post-RC1 branch for cognitive reintegration.

Exit gate:

- no RC1 runtime regression;
- no historical branch merged wholesale;
- every recovered mechanism has an explicit current invariant.

## Phase R1 — Structural trajectory substrate

Recover the valuable core of Address-Trajectory V2 over the *current* RC1 structural IDs.

Implemented in the first reconciliation slice:

- immutable occurrence trajectories;
- hierarchy isolation;
- immediate identical-address loop collapse;
- deterministic replay/idempotency;
- structural overlap/order/adjacency matching;
- exact forward and reverse occurrence-local frontier;
- competing continuations preserved;
- no cross-occurrence hub stitching;
- query read-only;
- direct import from current StructuralObservationStore.

Important change from the old laboratory implementation:

- text token hashing is **not** the canonical trajectory layer;
- the canonical layer consumes opaque structural addresses;
- text/audio/video/sensor adapters remain upstream.

Exit gate:

- all R1 tests green on Linux/Windows;
- current RC1 structural tests remain green.

## Phase R2 — Durable trajectory + evolving address state

Recover persistence lessons from the topological/BDR experiments and add a first-class
stable address state journal.

Target:

```
address A
  identity: stable
  revision: monotonic
  state(t): variable
  payload refs: variable
  trajectory refs: append-only
  provenance refs: append-only
```

Requirements:

- BDR-backed cold reopen;
- no destructive overwrite of old state;
- explicit current/history projection;
- forward/reverse transition traversal;
- crash/replay idempotency.

### R2 implementation slice

The first R2 implementation introduces:

- `ContentAddressedStatePersistence` as a small BDR/SQLite durability primitive;
- `PersistentStructuralTrajectoryRuntimeV2`, with a checkpoint cursor into the
  canonical StructuralObservation sequence;
- deterministic cold reopen and suffix replay when raw observations advance beyond
  the last trajectory checkpoint;
- `EvolvingAddressStateJournalV2`, where one stable opaque address can accumulate
  immutable revisions without deleting prior payloads;
- `PersistentEvolvingAddressStateJournalV2`, where each acknowledged revision is
  content-addressed in BDR/SQLite and referenced by an fsynced append-only index;
- previous/next/history traversal over revisions;
- hierarchy isolation;
- exact replay idempotency and rejection of conflicting same-sequence revisions.

Important semantic boundary:

`current_revision` is an operational navigation pointer to the latest admitted
revision. It is **not** a truth verdict and does not delete or invalidate competing
historical evidence. Truth/attractor resolution remains a later phase.

R2 gates include SQLite cold reopen on every CI platform and optional native-BDR
cold reopen when the native extension is available.

## Phase R3 — Hierarchical composition and multiscale convergence

Recover recurrent composition without linguistic labels.

Mechanisms:

- recurrent contiguous structures -> reusable composed addresses;
- bounded recursive composition;
- no destruction of atomic trajectory;
- cross-scale matching;
- false-consensus adversarial gates;
- density/hub diagnostics.

### R3 implementation slice

The first R3 implementation recovers hierarchical composition and multiscale
resolution over the reconciled opaque trajectory substrate.

Added mechanisms:

- deterministic recurrent compositions over opaque structural addresses;
- promotion only when a contiguous pattern is supported by multiple distinct
  trajectory occurrences;
- recursive composition of compositions;
- derived views only: atomic trajectories are never rewritten;
- hierarchy isolation;
- deterministic longest-first collapse;
- multiscale query/candidate views across depth 0 + derived depths;
- atomic structural evidence always dominates hierarchical reinforcement;
- zero-atomic-overlap candidates are rejected even if derived structures exist;
- structural density/hub profiles are exposed as diagnostics only.

R3 deliberately does **not** turn dense addresses into stopwords, delete hubs, or
assign density a truth weight. Density may inform later attractor diagnostics, but
does not participate in the R3 ranking key.

False-consensus gates include:

- recurrence repeated within one trajectory cannot promote a composition when
  independent-trajectory support is required;
- identical patterns observed once in separate hierarchy IDs do not combine;
- a derived scale cannot outrank stronger atomic evidence;
- unrelated queries remain unresolved despite recurrent compositions;
- hierarchy rebuild after cold reopen is deterministic.

## Phase R4 — Branching, rollout and recovery

Recover the strongest trajectory mechanics from the old V2 lab:

- structural frontier;
- competing branches;
- multi-step occurrence-local rollout;
- ephemeral branch filtering by new observations;
- explicit exhaustion;
- fresh-region recovery;
- hard gate: zero cross-occurrence stitching violations.

### R4 implementation slice

The first R4 implementation recovers forward frontier, branching, bounded rollout,
dynamic branch narrowing, exhaustion and fresh structural recovery.

Added mechanisms:

- occurrence-local rollout from the structurally strongest atomic candidates;
- multiscale support carried as secondary evidence without overriding atomic support;
- explicit rollout witnesses `trajectory_id + anchor_index`;
- common-prefix exposure before real branch divergence;
- terminal occurrences remain explicit outcomes when equally supported continuing occurrences also exist;
- frontier aggregation when independent occurrences predict the same next address;
- dynamic branch narrowing by new observations;
- adjacent duplicate observations do not consume an extra transition;
- eliminated hypotheses never mutate or delete stored trajectories;
- fresh recovery only after the active branch set is exhausted;
- recovery searches the new observed configuration from longest suffix to shorter
  suffixes only when the longer suffix is absent from memory;
- recovery preserves a terminal outcome beside continuing outcomes when both are
  witnessed by the same longest observed suffix;
- repeated copies of the same recovery suffix inside one stored occurrence use one
  canonical rightmost witness, preventing one trajectory ID from representing two
  contradictory cursor positions at once;
- fail-closed candidate/branch limits so operational bounds cannot silently select
  a subset of structurally tied futures.

Critical anti-stitching change from the historical V2 laboratory:

If the longest observed recovery suffix **exists** in memory but every matching
occurrence is terminal, recovery stops with `recovery-matched-terminal`. It does
not shorten the suffix and jump into another occurrence through a shared hub.

R4 branch state remains ephemeral and read-only. Persistent memory contains the
observations/trajectories; active hypotheses are a temporary inference view.

## Phase R5 — Attractor dynamics

Combine the modern RC1 continuous association field with trajectory evidence.

Inputs may include:

- direct structural overlap;
- ordered/adjacent trajectory support;
- recurrence;
- temporal/physical distance;
- structural density;
- forgetting/decay;
- independent provenance support;
- trajectory continuity;
- competition/contradiction.

No domain-specific semantic weight table is allowed.

The attractor layer must expose its evidence components for diagnostics.

### R5 implementation slice

The first R5 implementation adds a conservative structural attractor layer over
the R4 frontier.

The attractor does **not** collapse heterogeneous evidence into a weighted scalar.
There is no formula such as:

```
0.4 * recurrence + 0.3 * temporal + 0.3 * similarity
```

Instead every candidate exposes independent evidence dimensions:

- supporting trajectory occurrences;
- atomic matched-address count;
- number of supporting hierarchy depths;
- within-event association support count and accumulated field mass;
- temporal association support count and accumulated field mass.

The current continuous structural association field already owns its recurrence,
distance, forgetting and optional physical-time dynamics. R5 reads those decayed
channel masses without learning from the query.

Candidate A dominates candidate B only when A is no worse on every active evidence
dimension and strictly better on at least one. If evidence crosses — for example,
more recurrent trajectories for A but stronger decayed association mass for B —
both remain on the Pareto frontier and the result is ambiguous.

Topological density remains diagnostic only and is deliberately excluded from the
dominance relation.

Terminal outcomes are not assigned artificial zero/negative scores. When an
equally supported terminal occurrence competes with a concrete next-address
candidate, R5 remains ambiguous. A terminal-only region is reported explicitly
without inventing a next address.

R5 gates include:

- recurrence-only attractor formation;
- equal evidence remains ambiguous;
- current continuous field can resolve an otherwise structural tie;
- crossed recurrence/decay evidence remains ambiguous;
- density cannot choose the attractor;
- terminal-vs-forward competition remains unresolved;
- terminal-only region is explicit;
- hierarchy isolation;
- unrelated query remains unresolved;
- bounded candidate set fails closed;
- query leaves both trajectory memory and association field unchanged.

## Phase R6 — Structural equivalence and reformulation

Recover the old equivalence experiment, but make it consume the reconciled trajectory/state substrate.

Rules:

- equivalence comes from repeated independent convergence;
- same-lineage replay is not independent support;
- equivalence is revocable;
- direct structural evidence has precedence;
- conflicting equivalences fail closed;
- query is read-only.

This is the main path toward paraphrase/generalization without requiring embeddings or an LLM.

## Phase R7 — Temporal state inference

Rebuild current/previous/change/history over stable evolving addresses.

Required no-LLM operations:

- current state;
- previous state;
- history;
- state transition;
- forward temporal neighbor;
- reverse temporal neighbor;
- competing temporal branches;
- no-answer/ambiguous state.

The implementation must not require a domain predicate such as `pet.name` to pass.

## Phase R8 — Resolutive Inference Engine v0

Create one read-only inference surface over:

```
query/event
  -> structural addresses
  -> trajectory activation
  -> multiscale evidence
  -> attractor candidates
  -> temporal/state traversal
  -> resolved/ambiguous/unresolved internal result
```

A result should contain addresses, trajectory IDs, candidate states, conflicts,
provenance and diagnostics before any text generation.

## Phase R9 — Decisive no-LLM benchmark

Disable external/model calls and gate:

- current vs previous state;
- competing evidence;
- recurrence dominance without deletion;
- paraphrase with reduced lexical overlap;
- distractors;
- multiple similar contexts;
- cold reopen;
- forward/reverse traversal;
- negative/no-answer cases;
- query immutability.

Historical Lotus/Vibe, shirt-color and similar device regressions return here as
**tests**, not as sources of special grammar rules.

## Phase R10 — Context Compiler v2

Recover the Context Compiler principle with a new schema.

Old form:

`subject / attribute / value`

New target:

`addresses / resolved state / trajectories / attractors / conflicts / provenance / uncertainty`

Raw text remains optional provenance/debug material, not the cognitive representation.

## Phase R11 — Epistemic response boundary

Recover useful parts of Response Validator and Learning Gate:

- every LLM claim remains separately identifiable;
- validation measures consistency, not truth;
- a model response cannot silently mutate authoritative memory;
- promotion/acceptance never rewrites the original candidate;
- audit/idempotency survives restart.

Change from the historical policy:

- provenance classes do not mechanically define truth;
- competing evidence may coexist;
- reinforcement, independence, temporal trajectory and later observations influence resolution.

## Phase R12 — Native/mobile/server cognitive ABI

Only after the new packet/result contracts are stable:

- compile cognitive result;
- validate response;
- submit explicit evidence/learning decision;
- preserve local/server provenance plane;
- expose origin diagnostics to OFF.IA;
- retain ABI compatibility when possible.

Do not resurrect the historical C implementation byte-for-byte.

## Phase R13 — bit.analyze multimodal convergence

Feed StructuralEvent / RealitySlice streams into the same trajectory and attractor substrate.

Target:

```
text/audio/video/image/sensor
       -> bit.analyze/adapters
       -> opaque structural addresses
       -> trajectories/state
       -> attractors
       -> inference
```

No modality-specific cognitive law belongs in Memoria.ia.

## Phase R14 — RAG control and progressive LLM reduction

Compare controlled RAG retrieval against the reconciled engine on:

- retrieval;
- current/previous state;
- temporal direction;
- conflict preservation;
- paraphrase;
- cold restart;
- context bytes/tokens;
- external calls;
- latency.

Track LLM responsibility explicitly:

1. retrieval + LLM reasoning;
2. Memoria state resolution + LLM reasoning;
3. Memoria temporal/conflict inference + LLM composition;
4. Memoria inference + LLM verbalization;
5. supported tasks with no LLM.

## Recovered research backlog (do not lose)

The following historical modules are explicitly preserved as future work. They are
not prerequisites for the first inference freeze, but their concepts/tests remain
part of the project lineage.

### Context/window dynamics — ADAPT after R4/R5

- `structural_context_observation_v2`
- `structural_context_recall_v2`
- `structural_context_admission_state_v2`
- `address_trajectory_conversation_v2`

Recover the idea of a context/window as an addressable, evolving state with its own
payload and trajectory. Do not restore it as a special text-only conversation object.

### Density, portals and structural attention — ADAPT after R3

- `topological_density_v2`
- `address_portal_resolution_v2`
- `structural_attention_v2`

Dense hubs remain observable topology, not stopwords or semantic classes. Attention
may prioritize bounded exploration but must not manufacture evidence.

### Structural abstraction and transfer — DEFER until R6 is stable

- `structural_configuration_signature_v2`
- `structural_witness_discovery_v2`
- `structural_relation_abstraction_v2`
- `structural_role_abstraction_v2`
- `composed_convergence_v2`
- `address_convergence_v2`
- `address_composition_v2`
- `structural_equivalence_resolver_v2`
- `structural_transfer_forecast_v2`
- `structural_intervention_transfer_v2`

These modules explore recurring structural roles, cross-trajectory convergence and
transfer without fixed semantic labels. Their tests should be revisited only after
the reconciled trajectory/equivalence substrate exists.

### Temporal regimes and passive causal structure — DEFER until R7

- `temporal_regime_v2`
- `temporal_regime_state_v2`
- `adaptive_temporal_regime_benchmark_v2`
- `contextual_temporal_regime_v2`
- `continuous_temporal_causal_buffer_v2`
- `temporal_causal_window_v2`
- `causal_configuration_signature_v2`

Recover as experiments over persistent temporal state, not as universal causal laws.

### Prediction, surprise and active information — DEFER until R8

- `prediction_error_v2`
- `active_information_v2`
- `branch_evolution_v2`
- `world_state_candidate_resolution_v2`

These become useful once the inference engine can produce explicit competing
predictions. Prediction error must update evidence only through a separate
observation/learning policy.

### Active causal experimentation — DEFER until passive inference is proven

- `active_causal_experiment_v2`
- `active_causal_loop_v2`
- `interventional_evidence_v2`
- `intervention_consequence_v2`
- `interventional_causal_pipeline_v2`
- `continuous_causal_pipeline_v2`

The valuable invariant is separation between hypotheses, intervention selection and
world observation. Memoria.ia must never invent a successful intervention outcome.

### Multiagent / situated cognition / Live.infinita adapters — DEFER to integration layer

- `interagent_causality_v2`
- `interagent_contrast_v2`
- `multiagent_live_gym_v2`
- `causal_multiagent_live_gym_v2`
- `situated_live_gym_v2`
- `situated_contextual_regime_v2`
- `contextual_live_gym_v2`
- `regime_aware_live_gym_v2`
- `live_cognitive_gym_v2`
- `live_infinita_adapter_v2`
- `adaptive_live_gym_benchmark_v2`
- `multi_regime_stress_v2`

The cognitive mechanisms belong in Memoria.ia; product/world-specific adapters stay
outside the core and must not introduce domain laws.

### Curiosity — ADAPT as server capability after uncertainty is explicit

- `structural_curiosity_v2`

Recover only after R8 can expose genuine unresolved/ambiguous attractors. Curiosity
should select information gaps from those diagnostics. Source acquisition/crawling
remains a server responsibility; it must not be embedded in the offline core.

### End-to-end historical resolvers — TEST-ONLY

- `end_to_end_resolver_v2`
- `end_to_end_structural_resolver_v2`

Preserve their scenarios and observability goals, but rebuild them on the reconciled
engine instead of carrying old fallback policy forward.

## Freeze policy for the next candidate

Do not create the next cognitive freeze until:

- RC1 regression baseline remains green;
- trajectory persistence survives cold reopen;
- no cross-occurrence stitching is demonstrated;
- hierarchical/multiscale false-consensus gates pass;
- attractor competition is reproducible;
- current/previous/change inference works without LLM;
- query immutability is proven;
- negative cases remain unresolved;
- all recovered historical capabilities are marked recovered, adapted, deferred or dropped;
- limitations and negative results are recorded.

## Immediate execution order

The next code slices are:

1. **R1** structural trajectory substrate — started in this branch.
2. **R2** durable trajectory + evolving address state.
3. **R3** hierarchical/multiscale composition.
4. **R4** branch/rollout/recovery.
5. **R5** attractors using the current continuous association field.
6. **R6/R7** equivalence + temporal state inference.
7. **R8/R9** no-LLM inference engine and decisive benchmark.
8. only then Context Compiler, response boundary and mobile/server ABI.

This order deliberately recovers the valuable historical work without allowing its older semantic policies to dictate the post-RC1 architecture.
