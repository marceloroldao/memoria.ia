# v0.61 — Capability frontier results

Status: experimental. The benchmark separates matched basic operations from advanced lifecycle capabilities instead of collapsing unlike systems into one scalar score.

Environment-specific reference execution, seed 57.

## 10,000 events / 1,000 items / 10,000 queries

| system | ingest µs/event | query µs/query | peak bytes |
|---|---:|---:|---:|
| hash | 0.6647 | 0.0845 | 50,936 |
| chronological | 0.8154 | 225.4903 | 725,787 |
| resolutive_lifecycle | 22.6124 | 10.1265 | 4,520,648 |

## 100,000 events / 5,000 items / 10,000 queries

| system | ingest µs/event | query µs/query | peak bytes |
|---|---:|---:|---:|
| hash | 0.7101 | 0.1375 | 222,056 |
| chronological | 0.9016 | 2,503.8572 | 7,074,496 |
| resolutive_lifecycle | 15.4237 | 10.8251 | 44,401,480 |

## Interpretation

`HashMemory` is the correct winner for the minimal aggregate-score contract: it is both faster and smaller.

`ChronologicalMemory` has inexpensive ingestion but query cost grows sharply because current-score reconstruction scans the event history. The resolutive lifecycle is much more expensive to ingest and store, but its current-score query remains near the same order of magnitude when the event stream grows from 10k to 100k.

The dominant resolutive cost is not mysterious: `MemoryLifecycle` appends a history record on every support/contradict operation for every reached layer. This preserves rich provenance but creates substantial allocation and write amplification.

## v0.62 target

Test a compact lifecycle representation that preserves:

- current layer strengths;
- active/inactive state;
- `ever_active` historical knowledge;
- activation/deactivation transitions;
- active and historical depth;

while avoiding storage of every ordinary support/contradict event in every layer.

The hypothesis is falsifiable: if transition-only history does not materially reduce memory/ingestion cost while preserving lifecycle behavior, it should be rejected.
