# Memoria.ia v1.0.0-rc1 — Release Candidate 1

Release date: 2026-08-30

## Summary

`v1.0.0-rc1` is the first publication candidate for the Memoria.ia v1 line.

It consolidates the validated Resolutive Memory research lineage with the deployable PC/server product layer and the native/mobile runtime path, while keeping post-v1 experimentation isolated from the release candidate.

The release architecture remains:

```text
application / OFF.IA / agent
          ↓
      Memoria.ia
          ↓
   Resolutive-DB / BDR
```

Memoria.ia owns memory semantics and state. Resolutive-DB owns durable persistence. Optional LLMs are consumers, not the authoritative memory store.

## Included capabilities

- persistent local-first memory state;
- organization and namespace isolation;
- provenance and authority lineage;
- conservative `HIT` / `MISS` / `UNRESOLVED` resolution;
- semantic, episodic, temporal and relation kernels;
- correction/supersession behavior with preserved lineage;
- PC/server FastAPI product boundary;
- Docker/Compose deployment;
- provider-neutral language-model adapters;
- metrics and context-selection instrumentation;
- integrity-checked backup/restore;
- native production runtime;
- Android arm64-v8a mobile ABI;
- durable native BDR persistence and restart recovery;
- indexed native resolution for large-memory workloads;
- reproducibility and release metadata gates;
- official Memoria.ia visual identity assets.

## Frozen candidate provenance

The functional candidate was frozen at:

`dc73cbcdddfe20e0729e7e6bdea4697f7e8308cd`

That commit integrated PR #112, which preserved ranking, confidence, provenance policy, ABI and BDR contracts while adding the indexed native resolve lineage.

The release branch adds publication metadata, version alignment, release documentation and current branding without importing post-v1 PR #116 runtime behavior.

## Validation evidence

The exact functional lineage used for this release candidate passed the recorded required gates before release preparation:

- Android mobile ABI: PASS;
- native production image: PASS;
- Ubuntu/Windows candidate regression: PASS;
- BDR Linux/Ubuntu/Windows integration: PASS;
- native 100 / 1k / 10k benchmark matrix: PASS.

Recorded 10k native resolve benchmark improvement versus the prior frozen baseline:

- p50: `693.233 ms -> 6.288 ms` (~110x);
- p95: `710.630 ms -> 6.391 ms` (~111x).

These figures are environment- and workload-specific benchmark evidence, not universal latency guarantees.

## Publication metadata

- Release version: `1.0.0-rc1`
- Python package version: `1.0.0rc1`
- License: Resolutive Research and Non-Commercial License (RRNCL) v1.0
- Author: Marcelo Roldão Matos
- ORCID: `0009-0003-6075-4680`
- RSMS compatibility: `1.0-rc.1`

A new archival DOI should be assigned to this publication. The v0.95 DOI must not be reused as the release DOI for v1.0.0-rc1.

## Why this is RC1 rather than final v1.0

The repository currently declares compatibility with `RSMS 1.0-rc.1`, and the published Resolutive Science baseline remains on that release-candidate specification.

Therefore Memoria.ia is published as `v1.0.0-rc1` rather than claiming final v1.0 compatibility prematurely.

Final v1.0 promotion requires:

1. successful release-candidate metadata and regression gates;
2. reproducibility from the public release state;
3. compatibility re-audit against stable RSMS;
4. no release-blocking regression found during RC use;
5. final archival metadata and DOI synchronization.

## Explicitly excluded from RC1

The following post-v1 work is not part of this release candidate:

- external/public knowledge learning from OFF.IA Curiosity (issue #114 / PR #116);
- autonomous curiosity policy;
- new MA2A federation transport;
- multimodal post-v1 expansion;
- new semantic-consolidation phases from the post-v1 roadmap.

Those features continue independently after this publication.

## Security boundary

This release candidate is not represented as independently production-security certified.

Authentication, isolation, integrity and negative-path controls exist and are tested, but no independent production security audit is claimed.

## Claims boundary

This release does not claim:

- artificial general intelligence;
- biological equivalence;
- replacement of general-purpose LLMs;
- universal O(1) semantic resolution;
- production-ready MA2A federation;
- security certification.

Claims are limited to the implementation, tests, benchmarks and reproducible evidence recorded in the repository.
