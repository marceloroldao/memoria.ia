# memoria.ia v0.96 — Semantic Scaling Experiment

Status: experimental, controlled synthetic corpus.

## Objective

Measure whether conservative non-neural semantic routing remains accurate as the number of registered concepts grows, and identify the first scaling bottleneck before introducing neural fallback or more complex indexing.

## Protocol

Synthetic concepts were generated with one registered anchor and one contextual alias per concept. Unknown queries were added as negative controls. Resolution used threshold 0.45 and minimum runner-up margin 0.05. Measurements were repeated over the same deterministic corpus.

The benchmark script is `experiments/semantic_scaling_v96.py`.

## Observed baseline

Representative local measurements:

| concepts | accuracy | false-positive rate | known abstention | mean latency/query |
|---:|---:|---:|---:|---:|
| 10 | 1.000 | 0.000 | 0.000 | ~0.14 ms |
| 25 | 1.000 | 0.000 | 0.000 | ~0.30 ms |
| 50 | 1.000 | 0.000 | 0.000 | ~0.58 ms |
| 100 | 1.000 | 0.000 | 0.000 | ~1.17 ms |
| 250 | 1.000 | 0.000 | 0.000 | ~2.98 ms |

These measurements are not general language benchmarks. The corpus is deliberately controlled and separable.

## Candidate-index ablation

A sparse contextual candidate index was added and compared against full concept scanning. On this corpus, many concepts share generic contextual tokens, so the candidate sets remained dense. The index did **not** produce a reliable latency improvement and was slightly slower at the largest tested scales in a representative local run.

Therefore:

- candidate indexing remains experimental;
- `SemanticRouterV96(indexed=False)` is the default;
- no scalability claim is based on the candidate index;
- the negative result is preserved rather than hidden.

## Interpretation

The first observed scaling constraint is not semantic accuracy in this controlled corpus but approximately linear query cost with concept count. Future optimization should target discriminative candidate selection or cached scoring while preserving conservative abstention and checking equivalence against the full-scan baseline.

No claim is made that the measured deflection rate corresponds directly to GPU, energy, or monetary savings. Those require matched end-to-end workloads with an actual external/neural fallback.
