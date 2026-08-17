# v0.63 — Compact lifecycle stress at one million events

## Goal

Test whether the transition-only `CompactMemoryLifecycle` remains operational at a larger event scale while preserving the intended multiscale lifecycle behavior.

## Workload

- 1,000,000 support/contradict events
- 20,000 item identities
- deterministic seed: 63
- 5 memory layers
- layer-local rate rule: `rate(L) = 2^-L`

## Local reference run

Observed in the development execution environment:

- elapsed: ~12.43 s
- throughput: ~80,453 events/s
- mean event latency: ~12.43 us
- peak traced memory: ~36.31 MB
- stored item identities: 20,000
- recorded state transitions: 133,368

These values are environment-dependent performance measurements, not universal performance claims. The experiment script is committed so the run can be reproduced on other machines.

## Functional regression

A controlled target memory was tested through three phases:

1. 32 support observations
2. 40 contradictory observations
3. 32 support observations

Observed lifecycle depths:

- after consolidation: active depth 4, historical depth 4
- after contradiction/deconsolidation: active depth -1, historical depth 4
- after reactivation: active depth 4, historical depth 4

Thus the compact representation retained historical activation while permitting functional deactivation and later reactivation.

## Interpretation

The compact design did not exhibit memory blow-up or functional collapse at one million events in this controlled run. The result supports continued scaling experiments but does not establish production scalability.

The next test should perform a multi-scale, multi-seed sweep and model empirical complexity versus event count and unique-item count. In particular, memory growth should be decomposed into persistent item state and transition-history growth.
