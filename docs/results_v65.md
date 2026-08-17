# v0.65 — Memory decomposition

The compact lifecycle was profiled under two controlled regimes across three deterministic seeds.

## Results

| Events | Items | Regime | Mean transitions | Mean latency/event | Mean peak memory | Mean bytes/item |
|---:|---:|---|---:|---:|---:|---:|
| 10,000 | 1,000 | stable | 3,265.7 | 8.85 us | 1.37 MB | 1,373 B |
| 10,000 | 1,000 | contradictory | 4,936.0 | 8.73 us | 1.44 MB | 1,445 B |
| 100,000 | 5,000 | stable | 20,281.0 | 9.87 us | 7.57 MB | 1,514 B |
| 100,000 | 5,000 | contradictory | 41,859.7 | 10.22 us | 9.33 MB | 1,865 B |

## Interpretation

The main memory-growth pressure is not the layer clock itself. Contradictory regimes create substantially more activation/deactivation transitions. At 100k events the contradictory workload produces about twice as many transitions as the stable workload and roughly 23% more bytes per item.

The reported `bytes_per_transition` metric should not be interpreted as the marginal size of one transition because total peak memory also includes dictionaries, item keys, layer-state objects and lists. It is retained only as a coarse normalization.

## Decision

v0.70 will target representation overhead:

1. replace per-layer transition tuple lists with a compact transition representation;
2. reduce per-layer Python object overhead where possible;
3. preserve active depth, historical depth, deconsolidation and reactivation exactly;
4. compare compact-v0.62 and packed-v0.70 on stable and contradictory workloads.

This is an experimental result, not a production performance claim.
