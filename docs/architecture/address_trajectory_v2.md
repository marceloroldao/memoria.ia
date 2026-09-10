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

## Next benchmark

Run the same resolver as the memory grows through 100, 1,000 and 10,000 trajectories. Measure:

- top-1 trajectory accuracy on a held-out labeled test set;
- top-k candidate recall;
- ambiguity gap between first and second candidate;
- query determinism before/after cold restart;
- query immutability (state checksum must not change);
- latency and memory growth.

The hypothesis to test is:

`more coherent experience trajectories -> greater structural discrimination -> better resolution`, without semantic regexes or learned weights.
