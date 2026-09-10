# Address-Trajectory V2 — Recovery After Exhaustion

Status: experimental / unqualified

Canonical development branch: `experiment/address-trajectory-v2`
Canonical design PR: #296 (draft) against `freeze/mobile-repeated-collection-recall-v1-integration-qualified`
Qualified restart3 baseline: `5fa39ea39ce9d09518e8b726f6297bf8db02ef1c`

The baseline is not modified by this experiment.

## Why this slice exists

Dynamic branch filtering can legitimately reach an empty active set when a new observation does not fit any currently predicted continuation. Exhaustion is not a truth judgment. It means only that the current active hypotheses do not explain the newly observed configuration.

Recovery therefore opens a **fresh structural retrieval episode** from the observed address configuration. It must not create a persistent edge joining the exhausted trajectory to the recovered trajectory.

## CI finding before recovery hardening

At experimental head `62e01f79a29e5172a82363440ecdd88fe5840002`, GitHub Actions run #375 failed the full Ubuntu regression with two V2 failures while the real-BDR parity job passed:

1. `test_frontier_finds_unseen_continuation_without_semantic_rules`
   - expected `lotus`
   - observed `vibe`
   - diagnosis: hierarchical-scale count could outrank stronger atomic address convergence, demonstrating the previously documented false-consensus risk.

2. `test_rollout_does_not_jump_between_occurrence_trajectories`
   - `a -> hub -> x` and `b -> hub -> y`
   - query `a hub` incorrectly exposed both `x` and `y`
   - diagnosis: rollout retained a weaker partial-overlap occurrence after a stronger occurrence had already converged.

The negative result is retained as evidence; it is not treated as a passed gate.

## Corrective rule

The repair introduces no semantic regex, vocabulary, embedding, neural component or learned scalar weight.

Structural ranking is lexicographic:

1. stronger atomic address convergence dominates weaker convergence;
2. hierarchical/multiscale agreement is secondary evidence;
3. equal structural support remains ambiguous;
4. a dense/hub address cannot make a weaker occurrence hitchhike into the active future;
5. once an occurrence is selected, rollout remains inside that occurrence.

This deliberately exposes rather than hides false hierarchical consensus.

## Recovery contract

After `active == ()`:

1. preserve the exhausted `BranchState`;
2. take the new observed address configuration;
3. collapse only immediate self-loops;
4. search stored occurrences for the **longest observed suffix that occurs contiguously**;
5. if found, open fresh active continuations from those exact occurrences;
6. if several exact occurrences have different futures, keep all as competing branches;
7. if no suffix has a known continuation, remain unresolved;
8. never write a new trajectory, edge, fact, truth label or reinforcement during recovery.

The shorter-suffix fallback is intentionally observable and bounded by the finite observed configuration. It exists to allow a current stream to regain a known region when the full recent configuration is novel. It is not a global graph traversal.

## Required recovery matrix

Implemented deterministic tests cover:

- exhaustion -> reseed in another known trajectory;
- no compatible trajectory -> unresolved;
- persistent memory immutability;
- no false global edge;
- cold-restart determinism;
- several consecutive recoveries;
- hyperdense/hub address isolation;
- modality-neutral address streams;
- recovery followed by a new bifurcation;
- recovery back to a trajectory that had been discarded in another active context.

Existing dynamic-state, rollout, frontier and independent prototype recovery tests remain in the full regression as additional negative/compatibility coverage.

## Scaling benchmark

`benchmarks/recovery_after_exhaustion_v2_benchmark.py` runs at 100 / 1,000 / 10,000 trajectories and records:

- exhaustion;
- recovery success;
- recovery latency;
- active branch count/survival;
- ambiguity after recovery;
- read-only behavior;
- deterministic cold restart;
- hub-induced false reseed count;
- Python peak allocation during corpus construction.

The benchmark output is uploaded by the experimental PR regression workflow on Linux.

## Current qualification state

Not qualified yet.

The latest experimental workflow must complete successfully after the structural fixes and recovery matrix are present. A passing test suite is necessary but not sufficient for comparison against restart3; scaling evidence and the negative metrics above must also be reviewed.

## Remaining risks

- **False consensus across hierarchy:** still a first-class falsification target. The current change prevents hierarchy from outranking stronger atomic coverage at the frontier, but broader adversarial composition corpora are still required.
- **Suffix recovery ambiguity:** a short suffix may legitimately exist in many occurrences. Recovery must expose ambiguity rather than collapse by hash/address ordering.
- **Dense address pressure:** a single hub remains a valid address and may be the only available suffix. In that case many branches may reopen; this must be reported as ambiguity, not silently resolved.
- **Candidate limits:** bounded retrieval can hide valid low-order occurrences at very large scale. Benchmarking must report this instead of treating absence as falsity.
- **Duplicate experimental recovery APIs:** `ExhaustionRecoveryResolver` and `TrajectoryRecoveryResolver` remain historical/experimental comparison paths. The architecture document currently designates `DynamicBranchStateResolver.recover_*` as the canonical path for this slice. Removal/consolidation should happen only after qualification.

## Promotion rule

Do not merge PR #296 and do not integrate into OFF.IA until:

- experimental regression is green on Ubuntu and Windows;
- real-BDR parity remains green;
- 100 / 1,000 / 10,000 recovery evidence is captured;
- hub-induced recovery errors are zero in the controlled benchmark;
- cold-restart determinism is confirmed;
- adversarial ambiguity remains visible rather than hash-collapsed;
- a formal comparison against restart3 is executed and recorded.
