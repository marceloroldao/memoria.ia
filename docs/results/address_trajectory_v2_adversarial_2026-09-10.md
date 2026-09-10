# Address-Trajectory V2 — adversarial structural findings

Date: 2026-09-10
Status: experimental, not qualified against restart3
Canonical PR: #296 (draft)
Baseline (must remain unchanged): `freeze/mobile-repeated-collection-recall-v1-integration-qualified` @ `5fa39ea39ce9d09518e8b726f6297bf8db02ef1c`

## Purpose

This record captures negative findings and the corresponding structural corrections. It deliberately does not reinterpret failures as success and does not promote the V2 experiment into the frozen/mobile path.

## Negative finding A — false hierarchical consensus

Observed risk: a trajectory with weaker atomic convergence could rank ahead of a stronger atomic match merely because recurrent compositions caused it to appear supported at more hierarchy depths.

This violates the intended rule that derived hierarchy is supporting evidence rather than an independent vote capable of outvoting the observed atomic configuration.

Correction:

- depth-0/atomic structural evidence now dominates the multiscale ranking lexicographically;
- hierarchy depth count and derived-scale evidence are considered only after atomic evidence is tied;
- no learned scalar weights, semantic regex, domain vocabulary or intent labels were introduced.

A dedicated adversarial test constructs a stronger atomic candidate (3/3 overlap, one depth) against a weaker candidate (2/3 overlap, three depths). The stronger atomic candidate must rank first.

## Negative finding B — hyperdense recovery truncation

Observed risk: after exhaustion, recovery may shorten the observed configuration to a suffix. If the suffix is a hyperdense address such as a hub, many structurally equal occurrence futures can be found. Applying `branch_limit` to that set would retain only an arbitrary bounded subset and would incorrectly make an operational truncation look like cognition.

Correction:

- recovery continues to prefer the longest contiguous observed suffix;
- recovery never stitches the exhausted occurrence to another occurrence;
- if a recovery seed exceeds `candidate_limit` or yields more distinct continuation branches than `branch_limit`, recovery now fails closed;
- fail-closed means `recovered_any = false`, `active = ()`, `exhausted = true`;
- the observation is not marked false and persistent memory is not modified.

This intentionally trades recall for epistemic/structural safety when the available geometry is insufficient to preserve all equivalent alternatives inside the configured bound.

## Regression evidence before adversarial extension

Experimental PR regression run #388 completed successfully on head `bbab31615e350308efb89ac410dd17fa3f3c12c1`:

- Ubuntu: 905 passed, 35 skipped;
- Windows: 905 passed, 35 skipped;
- BDR/topological parity: success;
- recovery scaling benchmark: success;
- recovery remained read-only and deterministic after restart;
- recorded hub-induced recovery errors in the existing recovery benchmark: 0.

The existing recovery benchmark reported approximate recovery latency on Ubuntu:

- 100 trajectories: 0.089 ms;
- 1,000 trajectories: 0.486 ms;
- 10,000 trajectories: 4.510 ms.

These numbers are run-specific observations, not performance guarantees.

## New recurring adversarial evidence

`benchmarks/adversarial_structure_v2_benchmark.py` is now part of the experimental CI path and records:

- whether a weaker atomic trajectory can manufacture hierarchical consensus;
- whether hyperdense recovery produces any false reseed;
- fail-closed behavior at 100, 1,000 and 10,000 hub trajectories;
- recovery latency;
- persistent-memory immutability;
- cold-restart determinism.

Expected invariants:

- `false_hierarchical_consensus = false`;
- `total_false_reseeds = 0`;
- all hyperdense overflow probes fail closed;
- all probes remain read-only;
- all probes remain deterministic after restart.

## Still-open risks

The following are not considered solved by this cycle:

1. A recurrent composition can still be structurally bad even when it does not outrank stronger atomic geometry. We still need corpus-level false-consensus measurement rather than only a ranking-boundary contract.
2. Fail-closed recovery under hyperdensity can increase unresolved rate. This is acceptable for now, but the unresolved/recall tradeoff must be measured rather than hidden.
3. The current V2 hierarchy is rebuilt from the stored corpus. Incremental maintenance and long-running temporal evolution are not yet qualified.
4. Candidate and branch limits remain operational bounds. Future work should expose overflow explicitly in state/diagnostics rather than encoding it only as exhaustion.
5. A formal V2 vs restart3 comparison has not yet been performed.

## Next experiment

Build an adversarial corpus where recurrent compositions are deliberately misleading while atomic trajectories remain discriminative. Measure at 100 / 1,000 / 10,000 trajectories:

- top-1 and top-k;
- false hierarchical consensus rate;
- unresolved rate caused by fail-closed recovery;
- false reseed rate;
- hub-induced recovery errors;
- branch survival and ambiguity;
- restart determinism;
- composition count and maximum depth;
- latency and memory growth.

Only after this corpus-level adversarial gate is green should the V2 be considered ready for a formal comparison against restart3.
