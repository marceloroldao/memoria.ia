# Memoria.ia Address-Trajectory V2

Status: experimental

This branch preserves the qualified restart3 baseline and isolates a new cognitive path based on reusable addresses and trajectory fit.

## Principle

The system must not infer meaning from hard-coded semantic regexes, fixed intent enums, or learned weights. Ingestion and query use the same decomposition pipeline. Resolution is performed by comparing the address geometry of the current input against stored trajectories.

## Core invariants

1. A question is decomposed exactly like any other input.
2. No semantic regex decides `name`, `color`, `sibling`, `owner`, or equivalent domain meaning.
3. No learned scalar weight is required to select a result.
4. Reused addresses, sequence, adjacency and trajectory overlap are the primary signals.
5. Low-information memory is allowed to return ambiguous or poor candidates; the engine must expose that uncertainty instead of hiding it behind rules.
6. Query execution must be read-only. Repeating a question cannot create or reinforce factual state.
7. Existing RC/restart3 code remains untouched; this V2 engine is additive until it outperforms the frozen baseline.

## Experimental flow

```text
INPUT / QUESTION
      |
      v
same deterministic decomposition
      |
      v
address sequence + local compositions
      |
      v
candidate stored trajectories
      |
      v
structural fit
(address overlap + order + adjacency)
      |
      v
ranked trajectory candidates
```

The first laboratory implementation deliberately does not attempt to know what words mean. It only compares reusable addresses and their ordering.

## Initial acceptance corpus

Stored experiences:

- `meu gato e da cor verde`
- `irmao de meu gato e Lotus`
- `meu carro e da cor azul`
- `irmao de meu amigo e Vibe`

Queries:

- `qual e irmao do meu gato` -> trajectory ending in `Lotus`
- `qual a cor do meu gato` -> trajectory ending in `verde`
- `qual e irmao do meu amigo` -> trajectory ending in `Vibe`
- `qual a cor do meu carro` -> trajectory ending in `azul`

These expectations are test labels only. They are not encoded as semantic rules in the engine.

## Topological black holes (Resolutive ontology metaphor)

The project may use **topological black hole** as an internal metaphor for an address that connects many otherwise distinct trajectories or contexts. This is not a claim about physical black holes or real-world physics.

Conventional language stopwords such as `de`, `e`, `a`, `the`, `of`, etc. are not removed by vocabulary lists. They remain first-class addresses. If they appear across many trajectories and connect many distinct neighbors, the topology itself reveals that they are hyper-connected.

The same principle is modality-agnostic. A recurrent audio pattern, visual primitive, sensor symbol or other reusable address can become hyper-connected for the same structural reason. The engine must therefore quantify topology, not hard-code language-specific stopword dictionaries.

For each address, the initial density engine exposes a structural vector rather than a learned scalar weight:

```text
D(address) = (
  number of distinct trajectories,
  number of distinct neighbor addresses,
  total occurrences,
  number of predecessors,
  number of successors
)
```

Ranking is lexicographic and deterministic in the first experiment. No semantic meaning is assigned to density by the engine itself.

### Immediate-loop rejection

A repeated identical input must not manufacture trajectory length or reinforcement.

Invariant:

```text
if incoming_address == current_cache_address:
    reject transition
    do not advance state
    do not reinforce memory
else:
    accept transition
    current_cache_address = incoming_address
```

Thus:

```text
de de de de de de de de
```

produces one accepted state transition for the run of identical addresses, not eight. If another address occurs and `de` appears later, it can be accepted again because the current cache state changed.

This rule is generic: it applies equally to words, symbols, audio units, image-derived units, sensors or any future modality represented by an address.

## Next benchmark

Run the same resolver as the memory grows through 100, 1,000 and 10,000 trajectories. Measure:

- top-1 trajectory accuracy on a held-out labeled test set;
- top-k candidate recall;
- ambiguity gap between first and second candidate;
- query determinism before/after cold restart;
- query immutability (state checksum must not change);
- latency and memory growth;
- density distribution of hyper-connected addresses;
- false shortcuts caused by dense addresses;
- rejected immediate-loop count;
- convergence quality before and after loop rejection.

The hypothesis to test is:

`more coherent experience trajectories -> greater structural discrimination -> better resolution`, without semantic regexes or learned weights.
