# memoria.ia v0.95.0 — Stable Research Release

Status: stable research release in the v0.95 line. This is not the final v1.0 architecture.

## Validation

Promoted from `v0.95.0rc1` after a clean Google Colab checkout on Python 3.12 completed the full release gate:

- 267 tests passed;
- 0 failures;
- command: `python scripts/release_gate_v95.py`;
- final output: `v0.95 release gate: PASS`.

## Included architecture

- online hierarchical lifecycle with `r_L = 2^-L`;
- bounded stability/plasticity with default `max_strength = 1.25`;
- consolidation, deconsolidation and reactivation;
- shared knowledge payloads resolved by multiple trajectories;
- multinodal and multimodal routing;
- private and collective memory routes;
- independent confidence/lifecycle state per route;
- conservative distributed consensus: `same`, `related`, `conflict`, `distinct`;
- atomic routed snapshots with checksum validation;
- compact MI93 storage/transport format;
- package-level public API through `ResolutiveMemoryAPI`.

## Public API

- `remember`
- `reinforce`
- `challenge`
- `recall`
- `route_status`
- `compare`
- `save`
- `load`

Package and API version: `0.95.0`.

## Scientific scope

The repository preserves positive, negative and inconclusive results. Measurements are workload-specific prototype evidence, not universal guarantees. The project does not claim general intelligence, biological equivalence, or replacement of general neural models/LLMs.

## Licensing

Licensed under Resolutive Research and Non-Commercial License (RRNCL) v1.0. Academic, educational and qualifying non-commercial research use is permitted under the license. Commercial use requires separate authorization. This is not an OSI-approved Open Source license.

## Resolutive Science traceability

- `resolutive-science` baseline: v0.1.1;
- governance reference: RSPS 1.0-draft;
- numbered RSMS compatibility: not claimed until a formal audited RSMS release exists.

## Next line

New architecture/features should proceed after this release in a post-v0.95 development line. The v0.95.0 tag should remain immutable as the reproducible baseline for this research release.
