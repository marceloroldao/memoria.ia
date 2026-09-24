# R9 — Decisive no-LLM benchmark

This benchmark gates the post-RC1 resolutive inference stack with all external/model
calls disabled.

## Invariants

- external_calls == 0
- llm_calls == 0
- semantic_projection == false
- queries are read-only and must not mutate stored trajectories/state
- ambiguity and no-answer are valid outcomes and must not be coerced into answers
- provenance and supporting trajectory IDs remain inspectable

## Required scenarios

1. current vs previous temporal state
2. competing evidence remains explicit
3. recurrence can strengthen an outcome without deleting competitors
4. reduced-overlap reformulation succeeds only when structurally witnessed
5. distractors do not override stronger direct structural evidence
6. multiple similar contexts remain separable or explicitly ambiguous
7. cold reopen preserves the same inference result
8. forward/reverse temporal traversal is consistent
9. negative/no-answer cases remain unresolved/terminal as appropriate
10. query immutability before/after inference

## Historical regression corpus

Lotus/Vibe, shirt-color, relative naming and repeated-collection cases are admitted
only as regression vectors. They must not introduce special grammar, lexical rules,
hard-coded facts, or model calls.

## Measurements

For each vector record:

- expected and observed status
- expected and observed address when applicable
- source tier
- competing addresses
- supporting trajectory IDs
- provenance IDs
- equivalence witness IDs
- conflicts
- bounded/terminal flags
- external_calls / llm_calls / semantic_projection
- state digest before and after query
- cold-reopen parity when applicable

Aggregate:

- resolvable accuracy
- ambiguity preservation
- no-answer precision
- cold-reopen parity
- query immutability rate
- external/model call count

## Gate

R9 passes only when:

- all invariant tests pass;
- external/model call count is exactly zero;
- query immutability is 100%;
- cold-reopen parity is 100% for persistence vectors;
- no negative/no-answer vector is fabricated into a resolved answer;
- all deterministic expected structural/temporal vectors pass.

This gate measures what Memoria.ia can infer from its own learned structural state.
It does not measure natural-language generation quality.
