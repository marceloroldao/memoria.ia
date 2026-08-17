# memoria.ia roadmap to v1.0

This roadmap defines maturity gates rather than version-number targets. A version advances only when its tests, limitations and reproducibility artifacts are recorded.

## Compatibility

The project must track the terminology and conventions of `resolutive-science`. Before v1.0, the repository must declare the exact RSMS compatibility version it implements.

## v0.65 — Memory decomposition

Goal: identify why compact-memory growth is slightly superlinear in the current Python prototype.

Exit criteria:
- measure fixed state cost per item/layer;
- measure marginal transition-history cost;
- compare stable and contradiction-heavy streams;
- preserve functional equivalence of compact lifecycle semantics.

## v0.70 — Storage and object-layout optimization

Goal: reduce Python-object and transition overhead without changing semantics.

Exit criteria:
- lower peak bytes/item than v0.64 baseline;
- no regression in retention/deconsolidation/reactivation;
- scaling exponent re-measured.

## v0.75 — Persistence and recovery

Goal: make compact memory restartable and auditable.

Exit criteria:
- durable snapshot or SQLite persistence;
- deterministic reload;
- corruption/recovery tests;
- compact and full-provenance modes remain distinct.

## v0.80 — Online/continual-learning benchmark suite

Goal: compare against conventional online-memory baselines under controlled regime shifts.

Exit criteria:
- retention curves;
- adaptation latency;
- catastrophic-forgetting proxy;
- reactivation accuracy;
- update latency and memory growth;
- multiple seeds and confidence intervals.

## v0.85 — Semantic and polysemy robustness

Goal: close remaining over-splitting and context-stability problems.

Exit criteria:
- sense consolidation stress tests;
- order invariance;
- mixed-domain and adversarial-context tests;
- negative results preserved.

## v0.90 — API and integration candidate

Goal: define a stable external interface suitable for use by other Resolutive projects, including future Neural Resolutive integration.

Exit criteria:
- stable read/write/query API;
- serialization contract;
- lifecycle and provenance modes documented;
- integration examples;
- backward-compatibility tests.

## v0.95 — Release candidate preparation

Goal: freeze behavior and perform publication audit.

Exit criteria:
- full test suite passes from a clean environment;
- benchmark scripts and seeds documented;
- LICENSE and README audited;
- CITATION.cff and ORCID metadata present;
- RSMS compatibility declared;
- limitations and known failures documented;
- Zenodo metadata prepared.

When all v0.95 criteria are met, development must explicitly announce: **“Esta versão já é candidata a publicação.”**

## v1.0 — Stable scientific release

v1.0 is created only after the v0.95 audit succeeds and the release is reproducible from the public repository.

Required release artifacts:
- tagged GitHub release;
- complete documentation;
- reproducible benchmark results;
- academic/research non-commercial license and separate commercial-use terms;
- Zenodo deposit and DOI;
- DOI and citation information added back to the README.
