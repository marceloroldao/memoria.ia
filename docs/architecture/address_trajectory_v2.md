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
11. Compositions may recursively compose into higher levels, but promotion is bounded by recurrence, cross-trajectory support, maximum depth and maximum catalogue size per level.
12. Resolution may occur simultaneously at atomic and hierarchical scales. No semantic level is preselected; agreement across scales is additional structural evidence.
13. A structurally matched trajectory exposes a frontier: the nearest unresolved continuation after the matched configuration, not necessarily the terminal token of the stored experience.
14. Several possible frontier continuations remain separate branch hypotheses until topology provides enough structural separation to collapse one. Equal structural evidence remains explicitly ambiguous.
15. Multi-step rollout follows each compatible stored occurrence without jumping through shared global addresses. The resolver exposes the longest common future prefix and the first real divergence between competing continuation paths.
16. New observations update only the active branch state. An incompatible branch may be removed from the current hypothesis set without deleting, rewriting or marking its stored trajectory false.

## Experimental flow

```text
INPUT / QUESTION / SENSOR STREAM
      |
      v
same deterministic address space
      |
      v
atomic address sequence ----------------------+
      |                                        |
      +--> recurrent compositions              |
              |                                |
              +--> compositions of compositions|
      |                                        |
      +------------ multiscale views <---------+
                       |
                       v
              occurrence trajectories
                       |
                       v
              structural convergence
      (overlap + order + discrete hops +
             cross-scale agreement)
                       |
                       v
              trajectory frontier
                       |
                       v
              multi-step rollout
      (stay inside each stored occurrence)
                       |
                       v
             shared future prefix
                       |
                 first divergence
                       |
                       v
              competing branches
                       |
                       v
              new observations
                       |
                       v
          ephemeral branch-state filter
      (survive / eliminate from current state)
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

may create a first-level composition:

```text
HC2_1(A(meu), A(gato)) -> hc2:...
```

If a higher-level sequence also recurs, the first-level composition can participate as a child:

```text
HC2_1(meu,gato) -> A(dorme)
HC2_1(meu,gato) -> A(dorme)
```

may create:

```text
HC2_2(HC2_1(meu,gato), A(dorme)) -> hc2:...
```

No semantic claim such as `owner`, `pet`, `noun phrase`, `event` or `entity` is attached. Each composition means only: **this ordered local address structure recurred often enough to receive a reusable address**.

The hierarchical engine is deliberately bounded:

- deterministic address derived from ordered child addresses and hierarchy depth;
- minimum occurrence count before promotion;
- minimum distinct trajectory count before promotion;
- configurable minimum and maximum child count;
- maximum hierarchy depth;
- maximum compositions per level;
- deterministic longest-first collapse;
- original atomic trajectories remain untouched;
- raw provenance remains untouched;
- hierarchy is fully rebuildable after cold restart.

The purpose is not compression alone. Higher-level addresses create shorter alternative paths through recurring regions while preserving the lower-level path for audit and alternative resolution.

## Multiscale convergence

`MultiscaleAddressResolver` evaluates the same query in depth 0 (atomic) and every hierarchy depth that actually exists. It does not choose a semantic level such as word, phrase, entity or concept.

For a candidate trajectory, each scale independently exposes a structural evidence tuple:

```text
E_depth = (
  address overlap,
  ordered overlap,
  maximum hops to terminal,
  total hops to terminal,
  trajectory length
)
```

A candidate supported at several depths gains a stronger multiscale position because independent structural views converge on the same stored occurrence trajectory. No scalar learned weight is added across levels.

Important guardrail: hierarchy agreement is not allowed to create facts. It only ranks already-stored trajectories. The query remains read-only and the atomic path remains available even when higher-level compositions exist.

This also creates a falsifiable risk: a bad recurrent composition can produce false cross-scale consensus. The benchmark therefore records distractor behavior and must reject the V2 design if hierarchical support systematically amplifies wrong trajectories.

## Trajectory frontier, branching and rollout

`TrajectoryFrontierResolver` does not assume that the terminal address of a stored experience is the answer. After locating the best matched configuration, it returns the nearest address not already represented in the query configuration.

Example:

```text
stored: alpha -> beta -> gamma -> delta
query:  alpha -> beta
frontier: gamma
```

`BranchingFrontierResolver` groups frontier candidates by continuation address. If several independent trajectories share the same first continuation address, they remain one branch until topology actually diverges.

`TrajectoryRolloutResolver` extends this rule beyond one step. Every compatible stored occurrence is followed forward independently, up to a bounded number of addresses. Paths are never stitched together through a shared hub.

Example:

```text
T1: alpha -> beta -> gamma -> delta
T2: alpha -> beta -> gamma -> omega
query: alpha beta
```

Rollout exposes:

```text
shared future: gamma
first divergence:
  branch T1 -> delta
  branch T2 -> omega
```

The shared prefix is therefore structural evidence common to all active continuations. Divergence begins only at the first address where the occurrence trajectories actually differ.

A critical anti-shortcut invariant is:

```text
T1: a -> hub -> x
T2: b -> hub -> y
query: a hub
```

must never yield `y`. Reusing `hub` may seed several candidate occurrences during retrieval, but once an occurrence trajectory is being rolled out, traversal stays inside that stored experience. This prevents false global-graph jumps through hyper-connected addresses.

Identical future sequences from multiple stored experiences are aggregated as one continuation path with several supporting trajectory IDs. Different future sequences remain separate branches. Queries remain read-only and rollout is deterministic after cold restart.

## Dynamic branch state under new observations

`DynamicBranchStateResolver` turns rollout into an ephemeral active state. It begins with all structurally compatible continuation paths and consumes later observations address by address.

Example:

```text
T1: alpha -> beta -> gamma -> delta
T2: alpha -> beta -> gamma -> omega
query: alpha beta
```

Initial active futures:

```text
gamma -> delta
gamma -> omega
```

After observing `gamma`, both remain active. After observing `delta`, only T1 remains compatible.

This does **not** mean T2 became false. T2 is only eliminated from the current branch state because it does not explain this particular observed continuation. The stored occurrence remains intact and may become relevant in another context or later query.

Unexpected observations may exhaust the current active set completely. Exhaustion means `none of the currently predicted stored continuations match`, not `the observation is invalid` and not `the old memories are false`. A future recovery mechanism may then open a new retrieval from the newly observed configuration rather than forcing an existing branch.

The branch state is read-only with respect to memory, deterministic after restart, and modality-agnostic once observations arrive as stable addresses.

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

## Scaling benchmark

The experimental battery covers 100, 1,000 and 10,000 trajectories and measures:

- top-1 trajectory accuracy;
- top-k candidate recall;
- ambiguity gap;
- determinism after restart;
- query immutability;
- latency and memory growth;
- density distribution of hyper-connected addresses;
- false shortcuts caused by dense addresses;
- rejected immediate-loop count;
- portal-aware versus density-blind ranking;
- modality-agnostic stream parity;
- reusable compositions discovered per level;
- atomic versus hierarchical trajectory length;
- nested composition count;
- total hierarchy depth reached;
- catalogue cap enforcement;
- hierarchy rebuild determinism;
- combinatorial growth under adversarial recurrent streams;
- multiscale support depth per candidate;
- false consensus from recurrent distractors;
- multiscale versus atomic ranking stability;
- frontier correctness when the continuation is not the stored terminal;
- number of competing branch hypotheses;
- equal-evidence ambiguity preservation;
- repeated-trajectory support for the same branch;
- first-real-divergence correctness;
- multi-step shared-prefix length;
- first divergence index;
- occurrence-continuity violations;
- identical-future aggregation;
- bounded rollout length;
- rollout determinism after restart;
- active branch count after each new observation;
- incompatible-branch elimination rate;
- unexpected-observation exhaustion rate;
- false memory mutation count (must remain zero);
- dynamic-state determinism after restart.

The hypothesis to test is:

`more coherent experience trajectories -> greater structural discrimination -> better resolution`, without semantic regexes or learned weights.
