# Core Autonomous Memory v0.98 Improvement Gate

Baseline: autonomous v0.97, already validated on Windows and Ubuntu.

v0.98 is an experimental improvement line. It must not replace v0.97 unless it improves discrimination without reducing retrieval correctness, abstention quality, determinism, persistence, or cross-platform behavior.

## Candidate improvements promoted from v0.96 experiments

1. Inverse document/concept frequency weighting so rare terms contribute more than ubiquitous terms.
2. Discriminative candidate priority based on rare shared terms.
3. Conservative ambiguity handling using both absolute threshold and runner-up margin.
4. Additional observability for indexed-memory count, raw candidate count, and discriminative ranking.

## Non-goals

- No neural network or embedding dependency.
- No LLM call for memory discovery.
- No claim that semantic discovery is O(1).
- No removal of the exact-address lookup path.

## Promotion gates

The candidate must pass all existing v0.97 tests plus adversarial tests for common-token noise, rare-token discrimination, ambiguity, conflict, open-set abstention, persistence, determinism, and at least 10k indexed memories.
