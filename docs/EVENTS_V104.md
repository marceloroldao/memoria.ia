# Memoria.ia v1.04 — Explicit Events

Experimental layer above v1.03 temporal state.

## Contract

A state-change event is created only when v1.03 certifies an explicit temporal transition. An unmarked incompatible assertion remains a conflict and MUST NOT be promoted to an event.

Each event preserves:

- deterministic sequence/event id;
- entity and predicate;
- previous current state;
- new current state;
- source memory id;
- original source text;
- observed timestamp.

The event log is optional and independently persistent. The v1.03 temporal and earlier autonomous-retrieval contracts remain unchanged.

## Promotion gate

- initial facts do not emit change events;
- explicit temporal changes emit exactly one event per changed predicate;
- unmarked conflicts emit no event;
- multiple changes preserve order and before/after continuity;
- event persistence/reload is lossless;
- v1.03 temporal tests remain green;
- full repository regression remains green on Windows and Ubuntu.
