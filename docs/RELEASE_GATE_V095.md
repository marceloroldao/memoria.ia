# memoria.ia v0.95.0rc1 — Release Gate

This document defines the gate for declaring the implementation a publication candidate.

## Required gates

- [x] Candidate public API documented.
- [x] Online support/contradiction lifecycle retained.
- [x] Consolidation, deconsolidation and reactivation regression tests exist.
- [x] Multitrajectory shared payload with independent route state exists.
- [x] Individual and collective routes coexist.
- [x] Conservative distributed consensus exists without automatic destructive merge for `related`.
- [x] Persistent routed graph supports atomic write and CRC validation.
- [x] Repeated save/load stress showed no observed state drift in controlled tests.
- [x] Snapshot scaling was approximately linear in controlled tests.
- [x] Compact transport format has corruption detection and controlled benchmarks.
- [x] High-entropy payload benchmark recorded the storage/CPU trade-off.
- [x] Negative results and limitations are documented.
- [x] LICENSE present in release branch.
- [x] README updated to current maturity.
- [x] CITATION.cff with author and ORCID present.
- [x] Package metadata aligned to `0.95.0rc1`.
- [x] Integrated end-to-end release-gate regression added.

## Remaining before v1.0

1. Run the full test suite in a clean environment and preserve the exact output.
2. Re-audit RSMS terminology and compatibility against the release version of `resolutive-science`.
3. Review packaging/import surface for accidental experimental-module dependencies.
4. Freeze known limitations and benchmark methodology.
5. Prepare final release notes and Zenodo metadata.
6. Only after the above pass, promote to v1.0 and assign DOI.

## Current classification

`v0.95.0rc1` is a release-candidate gate. It must not yet be represented as v1.0 stable.
