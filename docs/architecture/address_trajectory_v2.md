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
8. Text is only one modality adapter. Audio, video, sensors and future inputs may supply precomputed address streams to the same topology engine.
9. Immediate identical-address loops do not advance state or reinforce a trajectory.
10. Recurrent contiguous address sequences may gain their own deterministic composition address. Composition is a derived view and never destroys the atomic trajectory or raw provenance.

## Experimental flow

```text
INPUT / QUESTION / SENSOR STREAM
      |
      v
same deterministic address space
      |
      v
atomic address sequence
      |
      +--> recurrent local compositions -> reusable composition addresses
      |
      v
candidate stored occurrence trajectories
      |
      v
structural convergence
(address overlap + order + discrete hops)
      |
      v
portal-aware collapse
      |
      v
ranked trajectory candidates
```

The laboratory implementation deliberately does not attempt to know what words or symbols mean. It only compares reusable addresses, ordering, occurrence trajectories, recurring compositions and topology.

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

## Reusable hierarchical address compositions

A recurring contiguous sequence of addresses may become a reusable higher-level address solely because it recurs in observed trajectories.

Example:

```text
A(meu) -> A(gato)
A(meu) -> A(gato)
```

may create:

```text
AC2(A(meu), A(gato)) -> ac2:...
```

No semantic claim such as `owner`, `pet`, `noun phrase` or `entity` is attached. The composition means only: **this address subsequence has appeared repeatedly as the same ordered local structure**.

Properties of the first composition engine:

- deterministic address derived from ordered child addresses;
- minimum recurrence required before discovery;
- same rule for text, audio, video and sensor address streams;
- longest recurrent composition selected first when several overlap;
- original atomic trajectory remains preserved;
- raw provenance remains preserved;
- cold restart rebuilds the same composition catalogue;
- query composition is read-only.

Compositions may themselves later become children of larger compositions, but recursive promotion is intentionally deferred until the first-level behavior is benchmarked. This avoids uncontrolled hierarchy growth before the topology is understood.

The experimental objective is not compression alone. A composition can create a shorter path through a stable recurring region:

```text
A(meu) -> A(gato) -> A(dorme) -> A(aqui)
```

becomes a derived view such as:

```text
AC2(meu,gato) -> A(dorme) -> A(aqui)
```

If a query also traverses `AC2(meu,gato)`, the same region can be reached with fewer discrete steps while preserving the lower-level route for audit and alternative resolution.

## Topological black holes (Resolutive ontology metaphor)

The project may use **topological black hole** as an internal metaphor for an address that connects many otherwise distinct trajectories or contexts. This is not a claim about physical black holes or real-world physics.

Conventional language stopwords such as `de`, `e`, `a`, `the`, `of`, etc. are not removed by vocabulary lists. They remain first-class addresses. If they appear across many trajectories and connect many distinct neighbors, the topology itself reveals that they are hyper-connected.

The same principle is modality-agnostic. A recurrent audio pattern, visual primitive, sensor symbol or other reusable address can become hyper-connected for the same structural reason. The engine therefore quantifies topology rather than hard-coding language-specific stopword dictionaries.

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

### Portal role instead of deletion

A hyper-connected address is not banned. It remains traversable and can still be a valid answer. The first portal-aware rule is deliberately conservative:

1. compare structural convergence first;
2. if one trajectory has stronger structural support, it wins regardless of terminal density;
3. only when structural support ties, prefer the less-dense terminal as the collapse point.

This means density acts as a topological role, not as a stopword penalty or learned weight. A dense address behaves more like a portal between many trajectories than a preferred destination, unless the trajectory evidence specifically converges on it.

## Immediate-loop rejection

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

produces one accepted address state for the immediate run, not eight. If another address occurs and `de` appears later, it can be accepted again because the current cache state changed.

Raw provenance is still preserved, so the original input can be audited even when the trajectory representation collapses immediate self-loops.

## Modality-agnostic streams

`AddressTrajectoryMemory.ingest_address_stream(...)` accepts precomputed addresses directly. This decouples the topology engine from text tokenization.

Example conceptual streams:

```text
text:   addr(meu) -> addr(gato) -> addr(verde)
audio:  audio:A -> audio:B -> audio:A
video:  visual:edge17 -> visual:hub3 -> visual:motion8
sensor: temp:bin21 -> temp:bin22 -> temp:bin21
```

All use the same immediate-loop rule, density engine, composition engine and occurrence-trajectory model. The modality-specific front end is responsible only for generating stable reusable addresses.

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
- convergence quality before and after loop rejection;
- portal-aware versus density-blind ranking;
- modality-agnostic stream parity;
- number of reusable compositions discovered;
- atomic versus composed trajectory length;
- atomic versus composed query hops;
- ambiguity before and after composition;
- composition catalogue determinism after restart.

The hypothesis to test is:

`more coherent experience trajectories -> greater structural discrimination -> better resolution`, without semantic regexes or learned weights.
