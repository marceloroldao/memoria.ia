# Topological/Temporal Memory — Freeze Review

Status: **GO for experimental freeze candidate**

Reviewed head: `99a1585d497b98f0fc6f360ec8f39e6771452827`
Branch: `experiment/topological-temporal-memory-v1`
PR: #276

## Decision

The experimental topological/addressable/temporal architecture is sufficiently validated to be treated as a **freeze candidate for controlled OFF.IA integration testing**.

This is **not** approval to merge the experiment into `main`, replace the frozen RC7 runtime, or change the stable product/mobile ABI. The freeze candidate should remain isolated while OFF.IA integration proves the adapter boundary in a real application path.

## Gates closed

The reviewed head passed all repository gates:

- full regression on Ubuntu;
- full regression on Windows;
- real BDR shared atomic ABI path;
- topological + epistemic restart fixtures;
- end-to-end cognitive restart fixture;
- Android mobile ABI;
- v0.96 semantic validation;
- product-alpha validation;
- product application credentials;
- layered performance baseline.

The cognitive restart fixture covers:

`ContextCompiler -> model response -> ResponseValidator -> LLM_GENERATED quarantine -> explicit Learning Gate validation -> separate trusted evidence -> EvidenceTemporalBridge -> BDR persistence -> restart -> factual CURRENT recovery + idempotency recovery`.

## Architecture accepted for the freeze candidate

### Persistent cognitive state

- deterministic reusable node addresses;
- hierarchical symbol/fragment/word/phrase/text composition;
- exact raw provenance preservation;
- append-only temporal events and transitions;
- monotonic internal sequence time separated from event/ingestion time;
- generic temporal operators;
- deterministic memory-resident query resolution;
- bounded graph activation.

### Epistemic boundary

Explicit source classes:

- `USER_CONFIRMED`
- `SENSOR_OBSERVED`
- `SYSTEM_INFERRED`
- `LLM_GENERATED`
- `EXTERNAL_PUBLIC`
- `DERIVED`

Only user-confirmed and sensor-observed evidence auto-promote by default. `LLM_GENERATED` has a hard promotion barrier. Model output can be recorded as evidence/audit but cannot directly mutate factual `CURRENT/HISTORY`.

### Learning Gate

A quarantined candidate is never rewritten or reclassified. Explicit validation creates a separate trusted EvidenceCore row linked to the original candidate and decision ID. Decision IDs remain idempotency boundaries after restart.

### Context Compiler

The compiled cognitive packet is bounded and excludes raw memory dumps and quarantined model evidence. It is read-only and contains only resolved facts, temporal information, relevant addresses/sequences and approved provenance.

### Response Validator

Model claims are classified as:

- `SUPPORTED_BY_CONTEXT`
- `CONFLICTS_WITH_CONTEXT`
- `UNVERIFIED`

All remain `LLM_GENERATED`; consistency is not authority. `response_id` survives BDR audit restart as an idempotency boundary.

### Persistence

Memoria.ia owns semantics. BDR owns binary/addressable persistence, atomic batches, durability and recovery.

Factual state and epistemic audit remain separated:

- `memoria.topology.v1/*`
- `memoria.epistemic.v1/*`

SQLite remains only a comparative oracle.

## Multi-size scaling evidence

The CI benchmark ran at 24, 240 and 1200 observations with semantic parity required and no performance pass/fail thresholds.

| Observations | Nodes | Node reuse | In-memory query p95 | BDR save | BDR reload | BDR bytes |
|---:|---:|---:|---:|---:|---:|---:|
| 24 | 168 | 0.9052 | 0.0082 ms | 6.25 ms | 3.59 ms | 97,715 |
| 240 | 868 | 0.9531 | 0.0217 ms | 27.44 ms | 30.20 ms | 774,042 |
| 1200 | 3,844 | 0.9591 | 0.0787 ms | 118.49 ms | 130.12 ms | 3,747,016 |

All three sizes preserved current-state, event-count, raw-count, topology-metric and transition-count parity between SQLite oracle and BDR.

## Positive findings

- deterministic duplicate-address count remained zero at all benchmark sizes;
- node reuse improved with scale;
- in-memory temporal query p95 remained below 0.1 ms at 1200 observations on the CI runner;
- BDR used materially less disk than SQLite in the measured fixtures;
- real BDR restart preserved cognitive and epistemic boundaries;
- generalization tests remain domain-independent;
- no neural network, embedding or LLM is required for deterministic memory/query tests.

## Negative findings / known risks

### BDR reload latency

At 1200 observations:

- SQLite reload: ~71.57 ms
- BDR reload: ~130.12 ms

BDR also saved slower at that size (~118.49 ms vs ~99.42 ms SQLite). This does not block the freeze candidate because semantic correctness and restart durability are preserved, but reload optimization is a concrete follow-up target.

### Dense hub pressure

The word `de` demonstrates dense-hub expansion pressure:

- 24 observations: 48 candidates, not truncated;
- 240 observations: candidate cap 64 reached, truncated;
- 1200 observations: candidate cap 64 reached, truncated, node degree 1202.

The rare token `xqz91` remained at 2 candidates throughout. This confirms that dense routing words need an explicit selectivity policy. No arbitrary ranking formula is frozen yet.

### Address algorithm

The current BLAKE2b-based `mt1:` address remains experimental. It is adequate for the prototype/freeze candidate but is not declared the final BDR/native address standard.

## Frozen interfaces for OFF.IA experiment

The controlled OFF.IA adapter should target these conceptual interfaces without bypassing them:

1. ingest trusted user/sensor evidence;
2. resolve memory through topological + temporal state;
3. compile a bounded `CognitivePacket`;
4. send only the packet/context to the language model path;
5. validate returned structured claims with `ResponseValidator`;
6. keep all model claims quarantined as `LLM_GENERATED`;
7. require Learning Gate validation before factual promotion;
8. persist topology and epistemic audit separately through BDR;
9. verify restart preserves factual state and idempotency boundaries.

## Explicitly outside this freeze

Do not freeze or standardize yet:

- final dense-hub selectivity/ranking formula;
- final native/BDR address algorithm;
- replacement of stable RC7/mobile ABI;
- automatic claim extraction from arbitrary model text;
- automatic promotion of external/public/model evidence;
- merging PR #276 into `main`;
- removing SQLite oracle before BDR convergence work is complete.

## OFF.IA readiness conclusion

**Ready for controlled experimental OFF.IA integration.**

The next stage should be an adapter/integration branch that preserves the validated Memoria.ia baseline and tests real conversation flows without changing the frozen cognitive contracts. Any integration regression must be attributed either to the adapter, OFF.IA orchestration, or the frozen Memoria.ia contract before modifying this branch.
