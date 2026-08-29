# Native server benchmark — v1 migration baseline

Accepted evidence for Issue #88 and PR #109.

- GitHub Actions run: `33270148076`
- PR head: `9b4b297e1dcd14c6d7299a3e73a137ccd6db4ff1`
- PR merge-test SHA recorded by the harness: `51a169658f56861049ca7f2ece066e7ae9098378`
- candidate base: `3cf3587ae2127e88637414defd79e620c492383c`
- Resolutive-DB pin: `1f6b7ccbe16bdfed2f1b5dcebceb17887bf6916e`
- runner: Ubuntu 24.04 / x86_64 GitHub Actions

| records | ingest p50 | ingest p95 | resolve p50 | resolve p95 | RSS peak | restart/load | context p50/p95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 0.414567 ms | 0.571824 ms | 0.135134 ms | 0.194920 ms | 45.477 MiB | 2.926600 ms | 25 / 25 B |
| 1,000 | 0.439418 ms | 0.585933 ms | 5.086863 ms | 6.687028 ms | 55.723 MiB | 18.668047 ms | 25 / 25 B |
| 10,000 | 0.444959 ms | 0.594831 ms | 693.232709 ms | 710.630051 ms | 226.934 MiB | 218.140401 ms | 25 / 25 B |

All three sizes passed the semantic correctness gates:

- every ingest produced one expected factual relation;
- every sampled resolve returned the expected source context;
- post-restart resolve returned the expected memory;
- durable store size remained stable across restart.

The run also validated the removal of the former fixed 256-turn ceiling. A dedicated native C regression stores 300 turns, closes, reopens through BDR and resolves after restart.

## Interpretation

Ingest remains essentially flat across the matrix. Selected context remains bounded at 25 bytes for this deterministic workload.

Resolve scaling is not acceptable as a final optimization target: the 10k run reaches ~693 ms p50. Current code materializes semantic candidates by traversing lineage for each stored turn; that path performs repeated full turn-array lookup and is effectively quadratic at scale. This performance follow-up is tracked separately in Issue #110 so the completed Python→native authority migration in #88 is not conflated with a new optimization project.

Raw accepted JSON is versioned beside this file as `native-100.json`, `native-1000.json` and `native-10000.json`.

## Issue #110 — memory-id index optimization

PR #111 removes the repeated full turn-array lookup from lineage resolution with an internal hash index keyed by `(namespace, memory_id)`. The index stores numeric turn/relation positions rather than pointers, so dynamic turn-array reallocation remains safe. Relation IDs are indexed too, preserving relation → turn → provenance-root traversal.

Measured on GitHub Actions run `33281856973`, merge-test SHA `146c66ef280e12257529926edd83a69b136dcbfa`, with the same BDR pin and deterministic workload:

| records | ingest p50 | ingest p95 | resolve p50 | resolve p95 | RSS peak | restart/load | context p50/p95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 0.422026 ms | 0.543602 ms | 0.091490 ms | 0.117839 ms | 45.176 MiB | 2.972094 ms | 25 / 25 B |
| 1,000 | 0.432708 ms | 0.587477 ms | 0.663809 ms | 0.884632 ms | 55.801 MiB | 18.468418 ms | 25 / 25 B |
| 10,000 | 0.431082 ms | 0.564490 ms | 6.288470 ms | 6.391282 ms | 227.746 MiB | 215.720600 ms | 25 / 25 B |

Relative to the frozen #109 baseline, resolve p50 improves about **7.7× at 1k** and **110× at 10k**; 10k p95 improves about **111×**. Ingest, selected-context size and restart/load remain effectively unchanged. All semantic, sampled-resolve, restart and durable-store validations remained green.

Because the lookup-only change removes the observed quadratic hot path, no lineage cache is introduced in this slice. Additional caching should only be considered if a later profile demonstrates a new bottleneck.
