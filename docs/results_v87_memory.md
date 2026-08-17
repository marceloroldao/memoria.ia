# memoria.ia v0.87 — Real RAM impact of multitrajectory sharing

The structural-sharing experiment was measured with Python `tracemalloc`, comparing:

1. `MultiTrajectoryMemory`: one payload per knowledge node, many routes referencing it;
2. a naive baseline: one independent payload object stored per route.

## Results

### 1,000 concepts × 8 routes

- shared representation: ~2.35 MB
- naive duplicated representation: ~6.00 MB
- measured RAM reduction: ~60.8%

### 5,000 concepts × 8 routes

- shared representation: ~11.60 MB
- naive duplicated representation: ~29.86 MB
- measured RAM reduction: ~61.2%

The logical payload-copy avoidance is 87.5% (1,000 payload nodes instead of 8,000 copies in the smaller case), but total RAM reduction is lower because route tuples, dictionaries, modality/provenance metadata and Python-object overhead remain allocated.

## Interpretation

The experiment supports the narrower claim that multiple private/collective and multimodal trajectories can share a single knowledge payload with a substantial reduction in total process memory compared with naive payload duplication.

It does not establish that all semantic memories can be safely merged. Identity is explicit through `knowledge_id`, and trajectory collisions or silent payload changes are rejected.

Next: combine shared knowledge nodes with independent trajectory evidence/lifecycle state so one bad or noisy route cannot automatically overwrite the shared semantic payload.
