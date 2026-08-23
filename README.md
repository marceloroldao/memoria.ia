# memoria.ia

Experimental implementation of **Resolutive Memory**, a memory architecture built around reusable knowledge nodes, multiple trajectories, online lifecycle dynamics, distributed consensus, and persistence.

## Enterprise product alpha

Active product branch: `product/enterprise-alpha`

The repository is being evolved incrementally into an installable PC/VPS/server product without replacing the validated research core. The current alpha layer includes:

- organization-scoped memory isolation;
- node and entitlement metadata boundaries;
- FastAPI `/api/v1` service;
- administrator and scoped application credentials;
- append-only logical memory versions and revocation;
- persistent restart/recovery;
- Docker/Compose deployment;
- minimal web chat/admin UI;
- provider-neutral LLM adapter with mock, Gemini and OpenAI implementations;
- per-request memory/context/token/latency/external-call metrics;
- baseline-vs-Memoria context comparison;
- live sanitized integration evidence for Gemini and OpenAI;
- validated product-state backup/restore with SHA-256 integrity and organization checks;
- dedicated product-alpha acceptance and CI workflows.

Semantic routing from v0.96 remains experimental and is not required for the exact-key product-alpha contract. MA2A federation/PKI also remains outside the local product-alpha boundary.

Product-alpha documentation:

- `docs/ENTERPRISE_ALPHA_GAP_ANALYSIS.md`
- `docs/SECURITY_ALPHA.md`

The alpha must not be described as production-secure. The HTTP status surface intentionally retains `security_status: not-security-reviewed` until the documented security gate is completed.

## Archived release

Latest archived release: **v0.95.1**  
Zenodo DOI: **10.5281/zenodo.21973472**

## Current maturity — v0.95 series

The v0.95 stable research line consolidates controlled experimental stages covering:

- hierarchical and temporal memory layers;
- online support/contradiction updates without neural retraining;
- consolidation, deconsolidation and reactivation;
- saturation-based stability/plasticity control;
- polysemy and sense-consolidation experiments;
- multinodal and multimodal trajectories;
- individual and collective memory routes;
- shared payloads with independent route confidence;
- conservative distributed consensus (`same`, `related`, `conflict`, `distinct`);
- atomic persistent snapshots with CRC validation;
- compact snapshot transport format;
- scaling, memory-cost, stress and continual-learning benchmarks.

The validated temporal rule remains:

`r_L = 2^-L`

with the v0.95 default configuration:

- levels = 5
- max_strength = 1.25

## Validation

The v0.95 implementation was promoted from `v0.95.0rc1` after a clean Google Colab checkout on Python 3.12 completed the full release gate:

- 267 tests passed;
- 0 failures;
- `python scripts/release_gate_v95.py`;
- final output: `v0.95 release gate: PASS`.

The `v0.95.1` release is a metadata-only citation interoperability fix over the validated v0.95.0 implementation.

## Install and test

Research baseline:

```bash
python -m pip install -e '.[test]'
python scripts/release_gate_v95.py
```

Product-alpha development install:

```bash
python -m pip install -e '.[product,test]'
python -m pytest -q
```

Container deployment is defined by `Dockerfile`, `compose.yaml` and `.env.example` on the product branch.

Representative recent experiments:

```bash
python experiments/compact_stress_v63.py
python experiments/scaling_v64.py
python experiments/stability_plasticity_v82.py
python experiments/stochastic_stability_v83.py
python experiments/multitrajectory_v87.py
python experiments/compact_snapshot_v93.py
python experiments/incompressible_snapshot_v94.py
```

## Public API

The v0.95 facade exposes:

- `remember(...)`
- `reinforce(...)`
- `challenge(...)`
- `recall(...)`
- `route_status(...)`
- `compare(...)`
- `save(...)`
- `load(...)`

See `docs/API_V090.md` and subsequent persistence/result notes.

The product branch wraps the stable memory facade behind a versioned HTTP/service boundary; experimental semantic-router internals are intentionally not part of the product-alpha API contract.

## Research status

The research line remains an experimental implementation, not a claim of general intelligence or a final v1.0 architecture. Claims are limited to controlled tests in this repository. Negative results, failed hypotheses and known limits are retained.

Important known limitations include:

- payload and trajectory persistence currently requires JSON-serializable values;
- compact snapshot compression depends on data redundancy and may trade CPU time for storage savings;
- semantic consolidation remains experimental and does not claim general language understanding;
- no claim is made that this replaces a general neural model or LLM;
- distributed consensus is conservative and deliberately avoids automatic destructive merge for merely related knowledge;
- the current Enterprise layer is a product alpha and has not completed a formal production security review.

## License

Source is publicly visible under the **Resolutive Research and Non-Commercial License (RRNCL) v1.0**. Academic, educational and non-commercial research use is permitted under its terms. Commercial use requires separate authorization. Because commercial use is restricted, this project should not be represented as OSI-approved Open Source.

## Resolutive Science compatibility

- Resolutive Science repository baseline: **v0.1.1**
- Project governance baseline: **RSPS 1.0-draft**
- RSMS compatibility: **candidate compatibility with RSMS 1.0-rc.1; re-audit required before stable v1.0**

Compatibility declarations must be re-audited and pinned before the v1.0 release.
