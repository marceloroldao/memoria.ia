# Memoria.ia v1.05 — Episodic Memory Gate

Status: experimental.

The v1.05 layer groups only certified v1.04 state-change events. It does not infer causality.

## Episode continuity rule

Two events may belong to the same episode only when all conditions hold:

1. same normalized entity;
2. same predicate;
3. previous `after` state exactly equals next `before` state.

Otherwise a new episode is started.

## Required gates

- single certified change creates one episode;
- continuous state transitions merge in temporal order;
- unmarked conflicts create neither event nor episode;
- different entities do not merge;
- episode projection preserves event IDs, memory IDs, source texts, start and end states;
- persisted events rebuild the same episode after restart;
- autonomous retrieval baseline remains functional;
- full regression passes on Ubuntu and Windows.

An episode is therefore a conservative projection over evidence-backed state transitions, not a claim of causal understanding.
