# Post-v1 — Node Ontogenesis and Branching

Status: architectural direction / backlog. Preserve the frozen RC5/v1 baseline; do not change validated behavior until this work is implemented and tested incrementally.

## Problem

The current memory engine already creates nodes across multiple structural layers, but the persistent memory model is still too close to raw text / byte-chunk storage and structural overlap.

For the intended Memoria.ia architecture, raw text may be preserved as provenance, but it must not be the only effective representation of memory.

The system should construct reusable addresses from the smallest stable units upward and reuse those addresses when the same symbol, token, concept, relation, or event reappears.

## Architectural principle

Memory ingestion should follow an ontogenetic path:

symbol -> fragment -> word/token -> expression -> concept -> relation -> event -> episode -> context

Each layer may have its own persistent node address.

Higher-order nodes should be composed from lower-order nodes rather than represented only as isolated text records.

## Example 1

Input:

`Hoje me acordei às 18h30.`

The original sentence may be preserved unchanged, but ingestion should also produce a graph such as:

- basic symbols / fragments;
- token `hoje`;
- token `me`;
- token `acordei`;
- token/time `18h30`;
- normalized concept/lemma `acordar`;
- relation linking the user to the action;
- temporal relation linking the event to `18h30`;
- composite event node representing the episode.

Illustrative structure:

```text
raw: "Hoje me acordei às 18h30"
                 |
                 +-- symbols/fragments
                 +-- word: hoje
                 +-- word: me
                 +-- word: acordei ----> concept: ACORDAR
                 +-- time: 18h30              |
                                             +--> event: user ACORDAR at 18h30
```

The important requirement is that `acordei` / `ACORDAR` receives a persistent reusable address.

## Example 2 — branching from an existing node

New input:

`Acordei de bom humor.`

This input should not become an entirely independent textual memory.

The system should resolve the existing node/address for `acordei` or `ACORDAR` and branch the new structure from that already-known node:

```text
                         [ACORDAR]
                         /       \
                        /         \
                 [18h30]       [bom humor]
                    |               |
                 event A          event B
```

This allows future retrieval to start from the concept/address itself rather than from a whole sentence.

## Identity and normalization

The architecture should distinguish at least:

```text
surface token: "acordei"
lemma: acordar
concept: ACORDAR
relation/event usage: user -> ACORDAR
```

These may be separate nodes linked together. They must not be collapsed blindly into one representation.

## Reuse rule

When ingesting new information:

1. preserve the raw source as provenance;
2. decompose the source into progressively higher-order units;
3. resolve whether each unit already has a persistent address;
4. reuse existing addresses whenever identity is sufficiently strong;
5. create only missing nodes;
6. branch new relations/compositions from reused nodes;
7. preserve occurrence, temporal, source, confidence, and provenance metadata;
8. keep contradictory or temporally updated states as events rather than silently overwriting history.

## Why this matters

Without this behavior, Memoria.ia is primarily storing documents and measuring structural overlap between them.

With this behavior, Memoria.ia becomes a persistent graph of reusable symbolic and conceptual addresses. New experiences increase the connectivity and density of existing nodes instead of creating isolated memories.

This is a key step toward making memory the persistent cognitive state of the architecture rather than a RAG-like text archive.

## Relationship with the future Context Compiler

Node ontogenesis builds memory bottom-up:

```text
raw input -> symbols -> nodes -> concepts -> relations -> events
```

The Context Compiler should activate memory top-down:

```text
question/intention -> entity/concept resolution -> active nodes -> relevant events/state -> compact cognitive package -> LLM
```

These mechanisms are complementary and should be designed together.

## Initial acceptance tests

A future implementation should include deterministic tests such as:

1. ingest `Hoje me acordei às 18h30.`;
2. assert that a persistent node for `acordei` / `ACORDAR` exists;
3. ingest `Acordei de bom humor.`;
4. assert that the existing `ACORDAR` node was reused rather than duplicated;
5. assert that both events branch from that node;
6. query from `acordei`, `acordar`, and an equivalent recognized form and verify convergence on the same concept node;
7. verify that the original raw sentences remain reconstructable as provenance;
8. verify that new branching does not mutate the historical event.

## Non-goals for the frozen baseline

- Do not replace the current storage engine immediately.
- Do not introduce neural embeddings as a requirement.
- Do not break byte-level reconstructability.
- Do not change the frozen RC5/v1 behavior without benchmark comparison and migration tests.

## Strategic direction

Long-term, the intended shape is:

```text
LLM = probabilistic language / difficult interpretation / broad knowledge
Memoria.ia = persistent state, identity, reusable addresses, relations, temporal history
Resolutive Engine = association, conflict resolution, inference, activation
```

The objective is to progressively reduce dependence on the LLM for memory organization while increasing deterministic symbolic/resolutive structure inside Memoria.ia.
