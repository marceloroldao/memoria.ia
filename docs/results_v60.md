# v0.60 — Multi-seed measured results

Status: experimental, negative/mixed result preserved.

The v0.60 statistical robustness experiment was executed from the current branch logic using eight deterministic seeds (`11, 23, 37, 57, 83, 101, 149, 211`) at two workload scales.

These measurements are environment-specific and are not publication-grade cross-machine benchmarks. They are useful for architecture triage and falsification.

## 10,000 events / 1,000 items

| system | quality mean | latency µs/event mean | peak bytes mean | utility/cost mean | utility 95% half-width |
|---|---:|---:|---:|---:|---:|
| hash | 0.953125 | 0.6505 | 50,825 | 0.96624 | 0.01049 |
| chronological | 0.953125 | 2.3694 | 597,174 | 0.14036 | 0.02323 |
| resolutive_lifecycle | 0.951923 | 12.7543 | 4,348,995 | 0.01849 | 0.00050 |

## 100,000 events / 5,000 items

| system | quality mean | latency µs/event mean | peak bytes mean | utility/cost mean | utility 95% half-width |
|---|---:|---:|---:|---:|---:|
| hash | 0.953125 | 0.6618 | 221,951 | 0.96129 | 0.00352 |
| chronological | 0.953125 | 0.6990 | 7,072,980 | 0.05798 | 0.00002 |
| resolutive_lifecycle | 0.951923 | 20.9187 | 44,244,006 | 0.00831 | 0.00040 |

## Interpretation

Under the v0.60 scalar `utility_per_cost` definition, the resolutive lifecycle is substantially more expensive and does not obtain a compensating capability score. This is a valid negative result for that metric.

However, the experiment also exposes a benchmark-design problem:

1. the four capability probes are too weak to discriminate the systems; all three obtain almost the same quality score;
2. ingestion latency is measured, while retrieval/query cost is not measured consistently;
3. `MemoryLifecycle` stores per-layer histories and activation state, while `HashMemory` stores only an aggregate scalar;
4. the scalar utility score therefore compares systems providing different semantic capabilities as though they implemented the same contract.

The conclusion is **not** that the resolutive architecture is superior or inferior in general. The supported conclusion is narrower: the current lifecycle implementation has a large time/memory overhead for basic event ingestion, and v0.60's utility metric is not adequate for capability-mismatched systems.

## Decision for v0.61

Replace the single utility ranking with a capability-frontier benchmark:

- Tier A: matched basic contract — support, contradict, current-score query;
- Tier B: historical/temporal contract — activation history, deactivation, reactivation, layer depth/regime state;
- report ingestion latency, query latency, memory, and supported capabilities separately;
- do not collapse unmatched systems into one scalar ranking.

This negative result is intentionally retained for scientific reproducibility.
