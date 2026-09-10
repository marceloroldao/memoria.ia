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
10. Recurrent contiguous address sequences may gain deterministic higher-level addresses; derived hierarchy never destroys atomic trajectory or raw provenance.
11. Recursive composition is bounded by recurrence, cross-trajectory support, maximum depth and catalogue size.
12. Resolution may occur simultaneously at atomic and hierarchical scales; no semantic level is preselected.
13. A matched trajectory exposes the nearest unresolved continuation rather than assuming its terminal token is the answer.
14. Competing continuations remain separate hypotheses until topology structurally separates them; equal evidence remains ambiguous.
15. Multi-step rollout follows each stored occurrence without jumping through shared global addresses.
16. New observations update only ephemeral branch state. Eliminating a branch does not mark its stored trajectory false.
17. Exhaustion reopens retrieval from the newly observed configuration. Recovery never stitches the exhausted occurrence to another occurrence through a shared hub and never manufactures a fact.

## Experimental flow

```text
input / question / sensor stream
        |
        v
 deterministic reusable addresses
        |
        +--> atomic occurrence trajectories
        +--> recurrent hierarchical compositions
        |
        v
 multiscale structural convergence
        |
        v
 trajectory frontier
        |
        v
 multi-step rollout
        |
        v
 competing active branches
        |
   new observation
        |
        v
 ephemeral branch filter
    |             |
 survives      exhausted
    |             |
 continue      fresh retrieval
                  |
                  v
          new compatible region
          or unresolved state
```

The laboratory implementation deliberately does not attempt to know what words or symbols mean. It compares reusable addresses, ordering, occurrence trajectories, recurring compositions and topology.

## Recovery after branch exhaustion

`TrajectoryRecoveryResolver` handles the case in which a new observation cannot be consumed by any currently active continuation.

Example:

```text
stored T1: alpha -> beta -> gamma
stored T2: zeta -> eta -> theta
current query: alpha beta
new observation: zeta
```

The active T1 prediction is exhausted by `zeta`. Instead of forcing T1, deleting it, or declaring `zeta` invalid, recovery opens a fresh retrieval seeded by the new observation. If the memory contains a compatible occurrence, T2 becomes the new active region.

The important invariant is that this is **re-retrieval, not trajectory stitching**. With:

```text
T1: a -> hub -> x
T2: b -> hub -> y
```

an exhausted T1 state cannot jump to T2 merely because both contain `hub`. Recovery starts from the complete newly observed configuration and retrieves stored occurrences again. Occurrence continuity remains intact inside each rollout.

If no stored trajectory explains the new observation, recovery returns unresolved. It does not create a new fact automatically. Learning/ingestion, if later permitted by policy, remains a separate operation.

Recovery is read-only, deterministic after cold restart, and modality-agnostic once stable addresses are supplied.

## Structural hierarchy and multiscale convergence

Recurring contiguous address sequences may receive reusable higher-level addresses. Compositions can themselves participate in higher compositions, but promotion is bounded. Original atomic trajectories and raw provenance remain untouched.

`MultiscaleAddressResolver` evaluates the same query at atomic and available hierarchical depths. Each scale exposes structural evidence such as address overlap, ordered overlap and discrete hops. Agreement across scales ranks already-stored trajectories; it does not create facts or semantic labels.

A bad recurrent composition can create false cross-scale consensus, so this remains a falsifiable risk in the benchmark rather than something hidden by semantic heuristics.

## Frontier, branching, rollout and dynamic state

`TrajectoryFrontierResolver` returns the nearest unresolved address after the matched configuration. `BranchingFrontierResolver` groups identical next addresses and preserves distinct continuations as separate hypotheses. `TrajectoryRolloutResolver` follows compatible occurrences multiple steps forward while forbidding cross-occurrence jumps.

For:

```text
T1: alpha -> beta -> gamma -> delta
T2: alpha -> beta -> gamma -> omega
query: alpha beta
```

rollout exposes the shared future `gamma` and only then the real divergence `delta | omega`.

`DynamicBranchStateResolver` consumes later observations address by address. After observing `gamma`, both branches survive; after observing `delta`, only T1 survives. T2 is removed only from the current hypothesis state and remains intact in memory.

Unexpected observations may exhaust the active set. Exhaustion means only that none of the currently predicted stored continuations explains the observation. Recovery then decides whether another stored region can explain it.

## Topological density and portal role

Hyper-connected addresses are not deleted or hard-coded as stopwords. Density emerges from topology: distinct trajectories, neighbors, occurrences, predecessors and successors. A dense address is treated as a portal role. Structural convergence dominates; density may break a structural tie but cannot override stronger trajectory evidence.

The project may call such hyper-connected regions `topological black holes` as an internal Resolutive ontology metaphor only; this is not a physical claim.

## Immediate-loop rejection

```text
if incoming_address == current_cache_address:
    reject transition
    do not advance state
    do not reinforce memory
else:
    accept transition
```

Immediate repeats therefore do not manufacture trajectory length or reinforcement. Non-immediate recurrence remains valid. Raw provenance remains available for audit.

## Modality-agnostic streams

`AddressTrajectoryMemory.ingest_address_stream(...)` accepts stable precomputed addresses, allowing the same topology to operate on text, audio, video or sensors. Modality adapters generate stable addresses; the trajectory engine itself remains modality-neutral.

## Scaling benchmark

The experimental battery targets 100, 1,000 and 10,000 trajectories and measures accuracy/recall, ambiguity, restart determinism, query immutability, latency/memory growth, density and false shortcuts, composition growth, multiscale false consensus, frontier correctness, branching behavior, rollout continuity, dynamic branch filtering and recovery behavior.

Recovery-specific measurements include:

- exhaustion events;
- successful fresh-region recovery;
- unresolved recovery;
- cross-occurrence stitching violations (must remain zero);
- memory mutation during recovery (must remain zero);
- recovery determinism after restart.

The hypothesis remains:

`more coherent experience trajectories -> greater structural discrimination -> better resolution`, without semantic regexes or learned weights.
