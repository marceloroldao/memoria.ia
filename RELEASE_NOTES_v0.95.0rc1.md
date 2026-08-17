# memoria.ia v0.95.0rc1 — Release Candidate Notes

Status: release-candidate gate, not stable v1.0.

## What this candidate contains

The v0.95 line consolidates the experimental work into one candidate public architecture:

- online hierarchical lifecycle with `r_L = 2^-L`;
- bounded stability/plasticity with candidate `max_strength = 1.25`;
- consolidation, deconsolidation and reactivation;
- shared knowledge payloads resolved by multiple trajectories;
- multimodal and multinodal routing;
- private and collective memory routes;
- independent confidence/lifecycle state per route;
- conservative knowledge comparison: `same`, `related`, `conflict`, `distinct`;
- atomic routed snapshots with checksum validation;
- compact MI93 storage/transport format;
- package-level candidate API through `ResolutiveMemoryAPI`.

## Public API candidate

The candidate API exposes:

- `remember`
- `reinforce`
- `challenge`
- `recall`
- `route_status`
- `compare`
- `save`
- `load`

The package version and API identifier are `0.95.0rc1`.

## Principal measured results retained from the research line

Controlled repository experiments found:

- compact lifecycle materially reduced Python prototype memory relative to the earlier full-history lifecycle;
- the compact lifecycle completed a 1,000,000-event stress workload without functional collapse in the measured environment;
- routed payload sharing reduced real RAM relative to naive repeated payload storage in the tested multitrajectory workloads;
- repeated routed snapshot save/load testing showed no detected state drift in the controlled v0.92 experiment;
- verbose snapshot growth was approximately linear with route count in the tested scaling range;
- MI93 compression strongly reduced snapshot size, including a high-entropy-payload benchmark, but with increased encoding CPU cost.

These results are workload-specific prototype evidence and are not universal performance guarantees.

## Important negative results

The project intentionally preserves failed or weaker approaches. Examples include:

- simple capability-per-cost scoring initially favored conventional baselines and exposed an unfair capability comparison;
- unrestricted lifecycle strength produced excessive retention and poor adaptation;
- direct temporal weighting did not solve semantic sense consolidation;
- simple hash memory remains preferable for workloads requiring only basic key/value aggregation.

See `docs/results_*.md` for individual experiment records.

## Reproducibility

Install and run:

```bash
python -m pip install -e .
python -m pytest -q
python scripts/release_gate_v95.py
```

Representative benchmark commands are listed in `README.md` and `REPRODUCIBILITY.md`.

## Licensing

This candidate uses the Resolutive Research and Non-Commercial License (RRNCL) v1.0. Academic, educational and qualifying non-commercial research uses are permitted according to the license. Commercial use requires separate authorization. The project must not be described as OSI-approved Open Source.

## Resolutive Science traceability

- normative repository baseline: `marceloroldao/resolutive-science` v0.1.1;
- governance reference: RSPS 1.0-draft;
- formal numbered RSMS compatibility: not yet claimed because no audited numbered RSMS release was identified during this gate.

## Before v1.0

The stable release still requires final complete-suite validation in a clean checkout, review of all release artifacts and third-party dependencies, immutable tag/release preparation, Zenodo metadata preparation, and DOI back-linking after archival deposition.