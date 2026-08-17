# memoria.ia v0.90 — Stabilization API

Status: pre-release stabilization contract. No v1.0 stability guarantee yet.

## Public facade

`ResolutiveMemoryAPI` exposes the candidate stable vocabulary:

- `remember(...)`: register one knowledge payload reachable through a trajectory;
- `reinforce(...)`: add supporting online evidence to one route;
- `challenge(...)`: add contradictory online evidence to one route;
- `recall(...)`: resolve a route, active-only by default;
- `route_status(...)`: inspect active and historical consolidation depth;
- `compare(...)`: classify two knowledge descriptors as `same`, `related`, `conflict`, or `distinct` without automatic destructive merge.

Default candidate configuration:

- levels: 5;
- max_strength: 1.25;
- temporal rate remains `r_L = 2^-L` in the underlying lifecycle.

## Stability boundary

From v0.90 to v0.95, new major architectural concepts should not be added to this facade. Internal implementations may be optimized or corrected while preserving the public semantics above.

Persistence is already experimentally validated for the packed lifecycle, but persistence of the complete routed/multitrajectory graph is not yet part of the v0.90 public facade. That is a release-candidate blocker and must be resolved before v0.95.

## Scientific discipline

`related` is not identity. Only explicit identity evidence may justify `same`. Negative benchmark results and known limitations remain part of the release record.
