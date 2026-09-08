# Post-v1 — Node Ontogenesis, Branching and Temporal Resolution

Status: **priority architectural direction / next evolution after the frozen RC5/v1 baseline**. Preserve the validated baseline; implement this work incrementally behind additive interfaces and benchmark it before replacing existing behavior.

## Problem

The current memory engine already creates nodes across multiple structural layers, but the persistent memory model is still too close to raw text / byte-chunk storage and structural overlap.

For the intended Memoria.ia architecture, raw text may be preserved as provenance, but it must not be the only effective representation of memory.

The system should construct reusable addresses from the smallest stable units upward and reuse those addresses when the same symbol, token, expression, concept, relation, event, phrase, or complete text reappears.

The next evolution must also introduce **internal temporal ordering and state transitions** so Memoria.ia can resolve questions such as:

`Qual era a cor da minha camisa?`

without depending on textual similarity or requiring the LLM to infer memory history.

## Architectural principle — every stable composition is an address

Memory ingestion should follow an ontogenetic path:

symbol -> fragment -> word/token -> expression -> phrase -> text/event -> concept -> relation -> episode -> context

Each stable unit at every layer may have its own persistent address.

Examples:

```text
"h"                       -> address
"ho"                      -> address
"hoje"                    -> address
"bom humor"               -> address
"acordei de bom humor"    -> address
complete text              -> address
```

A higher-order address must preserve its composition path through lower-order addresses.

Thus `hoje` is simultaneously:

- one address at the word layer; and
- a composition/path such as `h -> o -> j -> e` when inspected from a lower layer.

The architecture must therefore support navigation both upward and downward through composition layers.

## Activation and branching

Activating an address should expose structures that depart from, arrive at, or compose through that address according to the active layer and query context.

Example: activating symbol `h` in the word-formation layer may expose branches such as:

```text
[h]
 ├── [ho]
 │    ├── [hoj]
 │    │    └── [hoje]
 │    └── [hom...]
 └── [hu]
      └── [humor]
```

Once `hoje` exists as a stable composition, upper layers should reuse the `hoje` address rather than rebuilding its entire symbolic path for every new phrase.

## Dense nodes and routing

Very frequent nodes such as `de`, `para`, `que`, articles, punctuation, or common symbols may accumulate extremely high branching density.

They must remain addressable because they carry structural information, but they should not dominate retrieval merely because they are frequent.

The architecture should distinguish at least:

```text
density      = amount of connectivity/branching
selectivity  = how strongly a node reduces the candidate space
```

A highly dense, weakly selective node should behave primarily as a **routing/transit node**, not as a strong retrieval attractor by itself.

Contextual paths and neighboring addresses should determine its useful meaning.

## Temporal dimension — sequence counter per memory event

Every memory entry/event should carry a monotonic sequence counter representing internal ordering.

The sequence is not required to be wall-clock time. Its fundamental role is to establish:

```text
smaller sequence = before
larger sequence  = after
```

Example:

```text
E12 / seq=12: minha camisa -> cor -> azul
E24 / seq=24: minha camisa -> cor -> preta
E31 / seq=31: minha camisa -> cor -> branca
```

The sequence counter belongs to the **occurrence/event**, not to the reusable node itself.

For example, the node `AZUL` remains unique while appearing in many temporally distinct events:

```text
[AZUL]
 ├── E12 camisa
 ├── E87 carro
 ├── E104 céu
 └── E390 camisa novamente
```

Where useful, wall-clock timestamps may coexist with the internal sequence:

```text
sequence_time   = deterministic internal ordering
wall_time       = external/real timestamp
```

The internal sequence must remain sufficient to establish before/after even when no reliable external timestamp exists.

## State transitions

Relations that can change over time should be represented as ordered state events rather than overwritten facts.

Example:

```text
seq=12: camisa -> cor -> azul
seq=24: camisa -> cor -> preta
seq=31: camisa -> cor -> branca
```

This yields an explicit transition history:

```text
AZUL -> PRETA -> BRANCA
 12      24       31
```

Derived temporal operations should include at least:

```text
current   = latest valid state
previous  = immediately preceding state
first     = earliest known state
history   = ordered state sequence
changed   = transition between consecutive states
```

Where possible, validity intervals may later be derived:

```text
azul   valid_from=12 valid_to=24
preta  valid_from=24 valid_to=31
branca valid_from=31 valid_to=open
```

## Query resolution example — “Qual era a cor da minha camisa?”

The query should not be treated primarily as a text-search request.

Each recognized unit activates an address or operator role:

```text
qual    -> query operator
era     -> previous/past-state operator
cor     -> attribute
minha   -> ownership relation to user
camisa  -> entity
```

Conceptual activation:

```text
[qual]
   |
   +--> [era] -------- temporal constraint: previous state
   |
   +--> [minha] ------ owner: user
   |       |
   |    [camisa] ----- entity
   |       |
   +----> [cor] ------- attribute
```

The topology then exposes candidate state events:

```text
camisa -> cor -> azul    E12 / seq=12
camisa -> cor -> preta   E24 / seq=24
camisa -> cor -> branca  E31 / seq=31
```

The temporal operator `era` constrains the resolution to the appropriate historical state rather than merely selecting the largest sequence.

For a query meaning "what was the color immediately before the current/latest state?", the resolver performs:

```text
1. resolve entity: user's shirt
2. resolve attribute: color
3. collect matching state events
4. order by sequence
5. identify current/latest state
6. select the immediately preceding valid state
7. return the resolved value and provenance
```

With the example above:

```text
current  = branca / seq=31
previous = preta  / seq=24
```

If only two states existed:

```text
seq=12 -> azul
seq=24 -> preta
```

then:

```text
"Qual é a cor da minha camisa?"  -> preta
"Qual era a cor da minha camisa?" -> azul
```

The natural-language surface response may be generated locally or by an LLM, but the **state answer itself must already be resolved by Memoria.ia**.

## Important temporal distinction

The architecture should be able to distinguish event time from ingestion/storage time.

Example, when the user says today:

`Ontem minha camisa era azul.`

The event refers to an earlier time even though the statement is ingested now.

Future temporal metadata may therefore include:

```text
sequence
valid_from
valid_to
event_time
observed_at
stored_at
```

The sequence counter remains the deterministic baseline ordering mechanism.

## Example — node reuse and branching

Input A:

`Hoje me acordei às 18h30.`

The original sentence may be preserved unchanged, but ingestion should also produce reusable addresses for symbols, tokens, compositions and the event.

The important requirement is that `acordei` / `ACORDAR` receives a persistent reusable address.

Input B:

`Acordei de bom humor.`

This input should resolve the existing node/address for `acordei` or `ACORDAR` and branch the new structure from that already-known node:

```text
                         [ACORDAR]
                         /       \
                        /         \
                 [18h30]       [bom humor]
                    |               |
                 event A          event B
```

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
6. create explicit composition/branch relations among addresses;
7. assign a monotonic sequence counter to the new event/occurrence;
8. preserve source, confidence and provenance metadata;
9. represent updates as ordered state transitions rather than destructive overwrite;
10. keep contradictory or competing states inspectable instead of silently erasing history.

## Relationship with the Context Compiler

Node ontogenesis builds memory bottom-up:

```text
raw input
  -> symbols
  -> compositions
  -> word/expression addresses
  -> relations
  -> temporally ordered events/states
```

The Context Compiler / resolver activates memory top-down:

```text
question/intention
  -> activate addresses/operators
  -> propagate through topology
  -> intersect entity + attribute + relation constraints
  -> apply sequence/temporal operator
  -> resolve state
  -> compact cognitive package
  -> optional LLM surface generation
```

The LLM should not be required to decide which historical state is canonical for simple deterministic cases.

## Priority prototype / acceptance test

The first post-baseline prototype should remain intentionally small and prove the architecture before broader migration.

### Phase A — address composition

1. ingest `Hoje acordei às 18h30.`;
2. verify reusable symbol and word addresses;
3. verify a unique address for `acordei`;
4. ingest `Acordei de bom humor.`;
5. verify that the existing `acordei` address is reused;
6. verify two distinct branches/events;
7. preserve reconstruction/provenance of both original sentences.

### Phase B — temporal state resolution

Ingest:

```text
seq=12: Minha camisa é azul.
seq=24: Minha camisa é preta.
seq=31: Minha camisa é branca.
```

Then verify deterministically, without rules specific to `camisa`:

```text
Qual é a cor da minha camisa?
-> branca

Qual era a cor da minha camisa?
-> preta   # previous relative to current/latest state

Minha camisa já foi azul?
-> sim

Qual foi a primeira cor conhecida da minha camisa?
-> azul

O que mudou na cor da minha camisa?
-> azul -> preta -> branca

Qual era a cor antes de ficar branca?
-> preta
```

The prototype should expose the internal resolution trace for tests:

```text
activated addresses
candidate paths
candidate events
sequence ordering
chosen temporal operator
resolved state
provenance
```

## Non-goals for the frozen baseline

- Do not replace the current storage engine immediately.
- Do not introduce neural embeddings as a requirement.
- Do not break byte-level reconstructability.
- Do not change the frozen RC5/v1 behavior without benchmark comparison and migration tests.
- Do not make generic high-frequency nodes (`de`, `que`, etc.) dominant retrieval attractors.
- Do not delegate deterministic temporal-state resolution to the LLM when Memoria.ia has enough information to resolve it.

## Strategic direction

This document defines the **next prioritized architectural evolution** after the current frozen baseline:

```text
LLM
= probabilistic language, difficult interpretation and broad external knowledge

Memoria.ia
= persistent addresses, topology, temporal state, provenance and reusable memory structure

Resolutive Engine
= activation, propagation, association, temporal resolution, conflict handling and inference
```

The intended cognitive flow becomes:

```text
input
 -> address activation
 -> topology propagation
 -> state candidates
 -> sequence/time resolution
 -> resolved cognitive state
 -> optional language generation
```

The objective is to progressively move memory organization, state history and simple reasoning out of the LLM and into deterministic Memoria.ia / Resolutive Engine mechanisms.
