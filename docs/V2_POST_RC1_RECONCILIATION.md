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

## Phase R3 — Hierarchical composition and multiscale convergence

Recover recurrent composition without linguistic labels.

Mechanisms:

- recurrent contiguous structures -> reusable composed addresses;
- bounded recursive composition;
- no destruction of atomic trajectory;
- cross-scale matching;
- false-consensus adversarial gates;
- density/hub diagnostics.

## Phase R4 — Branching, rollout and recovery

Recover the strongest trajectory mechanics from the old V2 lab:

- structural frontier;
- competing branches;
- multi-step occurrence-local rollout;
- ephemeral branch filtering by new observations;
- explicit exhaustion;
- fresh-region recovery;
- hard gate: zero cross-occurrence stitching violations.

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
