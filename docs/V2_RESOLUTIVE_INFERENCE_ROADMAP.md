# Memoria.ia V2 — Evolution Roadmap: Memory to Resolutive Inference

Status: proposed execution roadmap  
Baseline: `bd33b9cfcfa78f0e3850fb5e298cbf4cbdc360b9`  
Date: 2026-09-23

## Objective

Evolve Memoria.ia from structural persistent memory/retrieval into a persistent state and inference substrate where progressively more reasoning happens over memory itself, before any LLM.

The target is not to replace one semantic retriever with another. The target is:

```
event/query
  -> structural decomposition
  -> address activation
  -> trajectories/state
  -> attractor dynamics
  -> resolutive inference
  -> cognitive result
  -> optional language model for interpretation/verbalization
```

An LLM must not be required to determine the internal result of the gates defined below.

## Non-negotiable principles

1. No rigid ontology, predicate vocabulary, grammar, or domain-specific correction rules in the early inference engine.
2. Conflicting observations may coexist. Do not implement "last write wins" as cognition.
3. Repetition, temporal distance, direction, structural recurrence, density and provenance may change attraction/authority.
4. Queries are read-only: asking something cannot reinforce its own answer.
5. LLM output is not automatically promoted to the same observational trail as user/sensor/external evidence.
6. Preserve provenance and history; a current attractor does not erase previous states.
7. Text is one input projection. The inference substrate must remain compatible with future StructuralEvent/RealitySlice multimodal input.
8. Every new cognitive capability requires an empirical gate, including negative cases.
9. Preserve the validated native/mobile ABI and BDR persistence baseline while evolving the cognitive layer.
10. Do not claim inference when the result is actually produced by an LLM or by a hard-coded semantic rule.

## Current validated baseline

The V2 structural runtime already provides a useful foundation:

- structural text observation and read-only resolution;
- reusable structural associations;
- recurrence-sensitive ranking;
- coexistence of conflicting observations;
- persistence/cold reopen through BDR;
- selectivity for unrelated queries;
- native/mobile structural ABI for OFF.IA.

This baseline is a structural retriever/state substrate. It is not yet the complete inference engine described here.

## Phase 0 — Freeze the empirical baseline

Before changing inference behavior:

- capture current structural gates as regression tests;
- preserve fact recall, conflict coexistence, recurrence ordering, unrelated-query rejection and cold reopen;
- record runtime/BDR/native ABI identities in test output;
- add explicit anti-regression checks that query resolution does not mutate reinforcement.

Exit gate: all existing V2 structural behavior remains reproducible from a clean/cold runtime.

## Phase 1 — Addressed evolving context

Introduce a first-class evolving address abstraction.

Concept:

```
Address A
  identity: stable
  state(t): variable
  payload(t): variable
  provenance: append-only references
  structural neighborhood: evolving
  trajectory refs: evolving
```

A conversation/window/session may be one address, but addresses must not be restricted to conversations. Later the same abstraction can represent an entity, device, environment, agent or multimodal context.

Requirements:

- stable address identity independent of mutable payload;
- version/state sequence;
- provenance for each transition;
- no forced semantic label such as person/pet/color;
- cold-reopen reconstruction.

Exit gate: mutate payload/state across observations while retaining address identity and reconstructing prior versions after restart.

## Phase 2 — Trajectory substrate

Represent change explicitly instead of treating memory as an unordered bag of observations.

Minimal form:

```
S(t0) --event/provenance--> S(t1) --event/provenance--> S(t2)
```

Requirements:

- forward and reverse traversal;
- temporal direction preserved;
- repeated structures reuse existing nodes where possible;
- old states remain addressable;
- trajectories can overlap/share structural segments;
- no domain rule for "name changed", "color changed", etc.

Exit gates:

- recover current structural state;
- recover previous structural state;
- traverse forward and backward after cold reopen;
- conflicting branches coexist rather than being deleted.

## Phase 3 — Attractor dynamics

Move from retrieval score toward explicit activation/attraction dynamics.

Candidate inputs to attraction:

- structural overlap;
- recurrence;
- temporal distance;
- temporal direction;
- association density;
- decay/forgetting;
- provenance/evidence channel;
- trajectory continuity.

These are dynamics, not semantic predicates.

The implementation must expose diagnostics showing why an attractor dominated without converting the diagnostic into a hand-authored semantic rule.

Exit gate: in a conflict sequence, recurrence/trajectory can make a newer repeated state dominant while the older state remains recoverable.

## Phase 4 — Resolutive Inference Engine v0

Create an inference path that returns an internal result before language generation.

Proposed output envelope:

```json
{
  "query_address": "...",
  "activated_addresses": [],
  "candidate_trajectories": [],
  "attractors": [],
  "resolved_state": null,
  "previous_states": [],
  "provenance": [],
  "diagnostics": {}
}
```

Do not require source text as the result. Source text may remain attached as provenance/debug material.

Initial inference capabilities:

- structural identity/context resolution;
- current-state resolution;
- previous-state resolution;
- change detection;
- recurrence-sensitive conflict resolution;
- temporal forward/reverse traversal.

Exit gate: these classes resolve without an LLM and without domain-specific semantic rules.

## Phase 5 — Decisive no-LLM benchmark

Build a benchmark that explicitly disables all LLM calls.

Core sequence example:

```
Meu gato se chama Alt.
Hoje comecei a chamar meu gato de Alt2.
Alt2 veio quando chamei.
Alt2 dormiu no sofá.
Alt2 veio comer.
```

Queries are converted to structural activation, but the benchmark judges the internal resolved address/state, not generated prose.

Required families:

- current vs previous state;
- repeated conflicting evidence;
- sparse conflicting evidence;
- unrelated distractors;
- multiple similar entities/contexts;
- restart/cold reopen;
- reversed temporal query;
- paraphrase with reduced lexical overlap;
- negative/no-answer cases.

Critical rule: do not add a special `pet.name`, `current_name`, grammar rule or equivalent merely to pass the benchmark.

Exit gate: measurable above-baseline inference using only Memoria.ia state/dynamics.

## Phase 6 — RAG control benchmark

Run a controlled comparison against a conventional retrieval pipeline.

Measure separately:

- retrieval accuracy;
- state resolution;
- previous-state resolution;
- conflict preservation;
- temporal direction;
- cold persistence;
- context size sent to LLM;
- LLM calls required;
- input/output tokens;
- latency;
- failure mode.

The goal is not to declare a winner. The goal is to identify which capabilities come from memory dynamics versus downstream language reasoning.

## Phase 7 — Cognitive package / Context Compiler

Once internal inference is useful, build a compact structured package for consumers:

```
Memoria.ia inference
  -> cognitive package
  -> optional LLM
```

The package should prefer resolved addresses, states, trajectories, uncertainty/conflict and provenance over dumping raw text chunks.

Measure how much raw context and LLM reasoning can be removed while preserving response quality.

## Phase 8 — Multimodal structural input

Connect bit.analyze only after the inference substrate is stable enough to accept modality-neutral events.

Target:

```
text/image/audio/video/sensor/raw bytes
  -> bit.analyze
  -> StructuralEvent / RealitySlice
  -> Memoria.ia addresses + trajectories
  -> resolutive inference
```

Memoria.ia must not need modality-specific cognitive laws. Modality-specific extraction belongs upstream.

Exit gate: temporal associations can combine events from at least two modalities while inference continues to operate on common structural primitives.

## Phase 9 — Local/server distributed state

After inference provenance is explicit, evolve local + server memory.

Requirements:

- every result identifies its memory plane/provenance;
- local private memory is not silently uploaded;
- server does not automatically override local state;
- merge/selection preserves conflicting evidence;
- stable addresses can reference changing payloads;
- synchronization policy is explicit and testable.

This prepares the substrate for MA2A without moving MA2A responsibilities into Memoria.ia.

## Phase 10 — Progressive LLM reduction

Track LLM responsibility as a metric.

Stages:

1. LLM performs reasoning + verbalization.
2. Memoria.ia resolves context; LLM reasons/verbalizes.
3. Memoria.ia resolves state/time/conflict; LLM composes/verbalizes.
4. Memoria.ia performs supported inference; LLM mainly verbalizes.
5. For supported tasks, deterministic/local verbalization can answer without an LLM.

Do not remove LLM use where the internal engine has not earned that capability through gates.

## Execution order

Immediate development order:

1. Phase 0 baseline lock.
2. Phase 1 addressed evolving context.
3. Phase 2 trajectory substrate.
4. Phase 3 attractor dynamics.
5. Phase 4 inference engine.
6. Phase 5 no-LLM benchmark.

Only after Phase 5 should we prioritize the RAG comparison, Context Compiler, bit.analyze multimodality and distributed local/server inference.

## Freeze policy

A new V2 inference freeze candidate should only be proposed when:

- baseline structural gates remain green;
- address identity/state survives cold reopen;
- trajectory forward/reverse gates are green;
- attractor conflict/coexistence gates are green;
- no-LLM inference benchmark has recorded reproducible results;
- negative results and limitations are documented;
- no benchmark-specific semantic rule was introduced.

## Definition of success

The key scientific/engineering result is not fluent text.

Success is demonstrating that Memoria.ia can take a new structural event/query, activate persistent state, traverse trajectories, resolve attractors and produce a useful internal state transition or answer candidate **without delegating that inference to an LLM**.

Language generation then becomes an optional consumer of the resolved cognitive state.
