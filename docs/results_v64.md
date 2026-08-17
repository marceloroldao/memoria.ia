# v0.64 — Compact lifecycle scaling

## Goal

Estimate empirical scaling of `CompactMemoryLifecycle` across increasing event and item counts while preserving the five-layer clock rule `r_L = 2^-L`.

## Measured points

The local execution environment completed the 10k and 100k multi-seed runs directly. The 1M point uses the already measured v0.63 stress result for the same compact lifecycle implementation.

| Events | Items | Latency (us/event) | Peak memory |
|---:|---:|---:|---:|
| 10,000 | 1,000 | ~11.24 | ~1.40 MB |
| 100,000 | 5,000 | ~10.64 | ~8.18 MB |
| 1,000,000 | 20,000 | ~12.43 | ~36.31 MB |

The first two rows are means over three seeds. The 1M row is the v0.63 measured stress point and is therefore not yet a three-seed estimate.

## Empirical exponents

Using a log-log least-squares fit on the three available scale points:

- latency vs event count: `p_T ≈ 0.022`
- peak memory vs item count: `p_M ≈ 1.10`

Interpreting `y ~ x^p`, the measured latency per event is approximately size-invariant over this range, while memory growth is close to linear but slightly superlinear.

## Interpretation

The latency result is encouraging: the compact lifecycle does not show evidence of history-length-dependent per-event slowdown across 10k to 1M events in this controlled workload.

The memory result identifies the next bottleneck. The excess over linear growth is plausibly associated with transition-list growth and Python object/container overhead, not the layer clock itself. This remains a hypothesis until transition density and per-item allocation are measured separately.

## Limitations

- The 1M point is inherited from the v0.63 run rather than rerun with all v0.64 seeds because the current execution sandbox has a strict per-command time limit.
- `tracemalloc` reports Python allocations and is not a complete process-RSS measurement.
- These are synthetic event streams, not production workloads.
- No claim of asymptotic complexity is made from three empirical points.

## Next test

v0.65 should decompose memory use into:

1. fixed per-item/layer state;
2. transition-history storage;
3. dictionary/container overhead;
4. effect of transition density under stable vs highly contradictory regimes.

The objective is to determine whether the observed `p_M ≈ 1.10` can be brought closer to linear without sacrificing deconsolidation, historical depth, reactivation, or layer-local clocks.
