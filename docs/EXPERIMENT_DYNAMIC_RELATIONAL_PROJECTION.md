# Experiment — Dynamic Relational Projection

Status: experimental, post-RC5

## Motivation

Memoria.ia relations must not be treated as a permanently flat graph of fixed triples. The same persisted evidence can participate in different relational projections depending on the current resolution state, query anchor, abstraction layer, provenance and active trajectory.

This experiment preserves the frozen v1.0.0-rc5 baseline and evaluates a post-RC5 hypothesis without changing the release candidate.

## Existing baseline

The current post-RC5 line already provides:

- persisted factual relations and provenance;
- layered factual abstractions;
- vertical dependency edges between abstraction levels;
- bounded relation-neighborhood traversal;
- directional native type collection;
- bounded two-hop relational activation before the LLM;
- query-aware relational ranking;
- query-focused composition of persisted relational chains;
- separate factual and generative memory spaces.

The experiment must extend these mechanisms rather than introduce a second relation system.

## Hypothesis

A relation is not only a stored edge `A -> predicate -> B`. During resolution it can be viewed as an evidence-bearing relation whose relevance, direction and projection are functions of the current state.

Conceptually:

`projection = P(evidence, query_state, layer_state, trajectory_state)`

The persisted evidence remains stable. What changes is the active projection used for resolution.

Example evidence:

- `Vivi is gato`
- `Lay is gato`

For `quem é Vivi?`, the active projection is entity-oriented:

`Vivi -> gato`

For `quais gatos você conhece?`, the active projection is type-collection-oriented:

`gato -> {Vivi, Lay}`

For `quantos gatos?`, the same projection is followed by a deterministic aggregate:

`gato -> {Vivi, Lay} -> count = 2`

No new factual edge needs to be persisted merely because the query changed direction.

## Important distinction

This is NOT a conventional rule engine of the form:

`if question == X: do Y`

and it is NOT a visual 3D feature for the Explorer.

The objective is to test whether the existing layered relational memory can expose different valid projections of the same evidence according to the current resolution state.

## Proposed resolution state

The experiment should model a transient, non-persisted `RelationalResolutionState` with fields such as:

- query anchors;
- requested relation family;
- requested direction;
- source abstraction level;
- target abstraction level;
- active trajectory/session context;
- provenance constraints;
- confidence threshold;
- depth/budget limits;
- candidate set;
- ambiguity state.

The exact representation is implementation-dependent. Do not persist query-specific projection state as factual memory.

## Projection classes

Start with a minimal set derived from already-supported behavior:

1. `FORWARD_ENTITY`
   - entity -> attribute/type/relation

2. `REVERSE_COLLECTION`
   - type/attribute -> matching entities

3. `COMPOSED_CHAIN`
   - bounded relation chain, currently max two hops

4. `INTER_LAYER`
   - traversal across existing abstraction levels

5. `AMBIGUOUS`
   - competing projections with insufficient evidence; fail closed

Do not add free-form geometric axes yet.

## Horizontal and vertical semantics

Use the existing abstraction model as the baseline:

- horizontal: relation traversal whose source and target remain at the same abstraction/support level;
- vertical: relation/dependency traversal that crosses abstraction levels.

The experiment should determine whether explicit orientation metadata is needed beyond the existing level and direction information. Do not assume a new `z` coordinate is necessary.

## Provenance barrier

Only factual-space evidence may participate in authoritative projection.

Unpromoted `assistant_generated` / generative-space content must never:

- become an authoritative projection source;
- change factual state;
- create a new persistent factual edge;
- resolve ambiguity by itself;
- reinforce its own previous generations.

This is a hard invariant.

## Primary benchmark: Vivi / Lay

Ingest factual evidence only:

- `Vivi é um gato.`
- `Lay é outro gato.`

Required behavior:

- `Quem é Vivi?` -> identifies Vivi as a cat.
- `Quem é Lay?` -> identifies Lay as a cat.
- `Vivi é o quê?` -> cat.
- `Lay é o quê?` -> cat.
- `Quais gatos você conhece?` -> Vivi and Lay.
- `Quais são os nomes dos gatos?` -> Vivi and Lay.
- `Fale o nome de dois gatos.` -> Vivi and Lay when this query is explicitly scoped to learned/personal memory; otherwise avoid conflating world knowledge.
- `Quantos gatos você conhece?` -> 2.

Negative invariants:

- OFF.IA must not become Vivi or Lay.
- OFF.IA must not claim to be a cat.
- a generated sentence such as `meu nome é Lay` must not enter factual memory.
- no query-specific reverse edge needs to be persisted to answer the collection query.

## Secondary benchmark: cars

Ingest:

- `Corsa é um carro e é verde.`
- `Jetta é um carro e é preto.`
- `Kombi é um carro e é preta.`

Required projections:

- entity -> color;
- car -> {Corsa, Jetta, Kombi};
- black -> {Jetta, Kombi};
- green -> {Corsa};
- `quantos carros pretos?` -> 2.

A generated wrong answer such as `Corsa é preto` must not contaminate factual projection.

## Measurements

Compare current baseline and experimental projection using:

- exact-answer accuracy;
- false positive rate;
- UNRESOLVED rate;
- ambiguity precision;
- number of persisted factual edges;
- number of transient projected edges/candidates;
- traversal depth;
- context characters sent to LLM;
- LLM calls avoided;
- CPU time and memory;
- deterministic reproducibility.

## Go / no-go criterion

Promote the idea only if dynamic projection improves reverse collection/composition or reduces prompt dependence without:

- increasing false factual recall;
- breaking direct factual HITs;
- weakening provenance isolation;
- introducing query-specific facts into persistent memory;
- materially increasing complexity without measurable benefit.

If no measurable gain appears, keep the RC5/post-RC5 relational baseline and discard the extra projection layer.

## Implementation sequence

1. Reproduce Vivi/Lay failure in a Core-only test without OFF.IA or LLM.
2. Verify current directional type collection behavior on the same evidence.
3. Add an explicit transient resolution-state representation only if needed.
4. Implement reverse collection/count as deterministic projection over persisted evidence.
5. Test same-layer versus inter-layer traversal separately.
6. Add generative contamination adversarial tests.
7. Benchmark against the current post-RC5 relational resolver.
8. Merge only after measurable improvement and regression parity.

## Non-goals

- no rewrite of Memoria.ia;
- no changes to frozen RC5;
- no arbitrary 3D coordinates;
- no LLM-based relation repair;
- no fixed synonym/rule explosion to make the benchmark pass;
- no persistence of transient query projections as facts;
- no weakening of fail-closed behavior.
