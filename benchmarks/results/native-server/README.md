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
