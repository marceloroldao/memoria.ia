# Context Compiler — experimental contract

## Purpose

The Context Compiler is the boundary between persistent cognitive state and any optional LLM.
It does not ask the LLM to search memory and it does not dump raw memory into a prompt.

Pipeline:

```text
question / sensor / intent
        |
        v
TemporalQueryResolver
        |
        v
Topological + temporal memory
        |
        v
ContextCompiler
        |
        v
bounded CognitivePacket
        |
        v
optional LLM / language surface
```

The LLM is downstream of retrieval/resolution. It is not the source of factual CURRENT/HISTORY state.

## CognitivePacket v1

The packet contains only the information needed to verbalize or reason over the resolved memory slot:

- original question;
- resolved temporal operator;
- resolved subject and attribute;
- requested value when the operator needs one;
- resolved boolean for existence queries;
- bounded factual rows;
- bounded state transitions;
- activated addresses;
- bounded candidate sequence identifiers;
- explicit counts of omitted history/candidates.

Factual rows may include:

- temporal sequence;
- subject / attribute / value;
- authoritative source class;
- evidence id;
- confidence;
- provenance;
- origin.

## Explicit exclusions

A CognitivePacket does **not** contain:

- raw memory text;
- full EvidenceCore history;
- quarantined `LLM_GENERATED` candidates;
- quarantined public/system/derived evidence;
- instructions to write the LLM answer back to memory;
- hidden automatic promotion semantics.

Raw memory remains available for provenance/audit outside this interface.

## Bounded context

`max_history` bounds history, transition and candidate-sequence material. The packet reports how much material was omitted rather than silently pretending that a bounded view is complete.

This protects the LLM boundary from context growth while preserving deterministic retrieval inside Memoria.ia.

## Epistemic behavior

Only events already admitted to the authoritative temporal track can appear as facts. Epistemic audit enriches those events with evidence metadata. Quarantined projections are ignored by the compiler.

Therefore a later `LLM_GENERATED` statement cannot override an earlier user/sensor fact simply because it is more recent or has high model confidence.

## Mutability

Compilation is read-only. It does not:

- create temporal events;
- alter transitions;
- promote evidence;
- apply Learning Gate decisions;
- change sequence counters.

Learning remains a separate post-response path governed by the explicit Learning Gate.

## Current status

This is an additive experimental interface on `experiment/topological-temporal-memory-v1`. It does not replace the RC7 runtime or current OFF.IA integration yet.
