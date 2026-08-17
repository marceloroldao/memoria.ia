# v0.85 — Temporal semantic consolidation

## Goal
Test whether recurrence-weighted consolidation reduces polysemy over-splitting while preserving non-destructive micro-sense history.

## Result
The first recurrence-weighted formulation was negative. On the controlled `banco` corpus, the original splitter produced about 6–7 micro-senses. Legacy consolidation produced roughly 2–4 groups depending on order when noise senses were included, while the recurrence-multiplied score typically retained 5–6 groups.

The failure is informative: multiplying the lexical link score by recurrence makes consolidation too conservative. Repeated evidence does not create semantic bridges between contexts that share few literal tokens.

## Interpretation
Temporal support can validate a semantic relation, but it cannot manufacture one. The next formulation must use second-order contextual structure (context-of-context / emergent ontology) to discover that distinct lexical neighborhoods can belong to the same macro-domain.

## Constraint
Micro-senses remain immutable source evidence. Any future macro-sense consolidation must remain derived and reversible.
