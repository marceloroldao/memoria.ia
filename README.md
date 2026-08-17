# memoria.ia

Experimental implementation of **Resolutive Memory**, a memory architecture built around reusable knowledge nodes, multiple trajectories, online lifecycle dynamics, distributed consensus, and persistence.

## Current maturity — v0.95.0rc1 gate

The project has progressed through controlled experimental stages covering:

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

The candidate temporal rule remains:

`r_L = 2^-L`

with default candidate configuration:

- levels = 5
- max_strength = 1.25

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
```

Representative recent experiments:

```bash
python experiments/compact_stress_v63.py
python experiments/scaling_v64.py
python experiments/stability_plasticity_v82.py
python experiments/stochastic_robustness_v83.py
python experiments/multitrajectory_v87.py
python experiments/compact_snapshot_v93.py
python experiments/high_entropy_snapshot_v94.py
```

## Candidate public API

The stabilization facade exposes:

- `remember(...)`
- `reinforce(...)`
- `challenge(...)`
- `recall(...)`
- `route_status(...)`
- `compare(...)`
- `save(...)`
- `load(...)`

See `docs/API_V090.md` and subsequent persistence/result notes.

## Research status

This is still a research prototype. v0.95.0rc1 is a **release-candidate gate**, not a final v1.0 release. Claims are limited to controlled tests in this repository. Negative results, failed hypotheses and known limits are retained.

Important known limitations include:

- payload and trajectory persistence currently requires JSON-serializable values;
- compact snapshot compression depends on data redundancy and may trade CPU time for storage savings;
- semantic consolidation remains experimental and does not claim general language understanding;
- no claim is made that this replaces a general neural model or LLM;
- distributed consensus is conservative and deliberately avoids automatic destructive merge for merely related knowledge.

## License

Source is publicly visible under the **Resolutive Research and Non-Commercial License (RRNCL) v1.0**. Academic, educational and non-commercial research use is permitted under its terms. Commercial use requires separate authorization. Because commercial use is restricted, this project should not be represented as OSI-approved Open Source.

## Resolutive Science compatibility

- Resolutive Science repository baseline: **v0.1.1**
- Project governance baseline: **RSPS 1.0-draft**
- RSMS compatibility: **pending a formally numbered RSMS release in `resolutive-science`**

The repository does not claim compatibility with a nonexistent or unpublished RSMS version. Once a numbered RSMS is released, this declaration must be re-audited and pinned before the stable v1.0 release.
