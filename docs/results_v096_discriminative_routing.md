# v0.96 — Discriminative candidate routing

## Objective

Reduce the near-linear lookup cost observed in the v0.96 full semantic scan without changing the final semantic score/acceptance rule.

## Method

A separate experimental router ranks candidate concepts using inverse concept frequency over contextual features. Rare contextual features contribute more than generic features. Only the top `candidate_limit` concepts are sent to the existing exact semantic scorer.

The benchmark intentionally keeps concept-specific features inside the configured context radius. An earlier benchmark draft placed those features outside the radius and was rejected as invalid before interpretation.

Controlled configuration:

- threshold: 0.45
- minimum margin: 0.05
- candidate limit: 32
- scales: 100, 250, 500, 1000 concepts
- up to 200 deterministic queries per scale

## Controlled result

An equivalent local execution of the benchmark logic produced:

| Concepts | Full accuracy | Discriminative accuracy | Mean candidates | Candidate fraction | Approx. speedup |
|---:|---:|---:|---:|---:|---:|
| 100 | 1.00 | 1.00 | 32 | 0.320 | 2.8x |
| 250 | 1.00 | 1.00 | 32 | 0.128 | 5.4x |
| 500 | 1.00 | 1.00 | 32 | 0.064 | 7.6x |
| 1000 | 1.00 | 1.00 | 32 | 0.032 | 9.6x |

The discriminative route matched the full-scan concept choice in this controlled corpus.

## Interpretation

This is evidence that rare-context candidate selection can reduce semantic lookup cost when concepts contain sufficiently discriminative local context. It is **not** evidence that a fixed top-32 candidate set is safe for arbitrary language or real-world corpora.

The earlier simple candidate index remains a negative result: generic context caused excessive candidate overlap and no reliable speedup. The discriminative approach improves that specific failure mode by down-weighting common features.

## Promotion criteria

Do not make discriminative routing the production default until all of the following hold on broader corpora:

1. recall parity with full scan is measured;
2. false-positive rate does not increase;
3. ambiguity/abstention behavior remains conservative;
4. latency advantage persists across repeated runs and larger vocabularies;
5. candidate-limit sensitivity is characterized.

Until then, `SemanticRouterV96(indexed=False)` remains the conservative reference implementation.
