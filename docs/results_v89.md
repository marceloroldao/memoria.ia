# memoria.ia v0.89 — Conservative Distributed Consensus

## Goal
Classify independently learned knowledge descriptors as `same`, `related`, `conflict`, or `distinct` without unsafe automatic semantic merging.

## Decision contract
- `same`: requires strong identity evidence via identical payload fingerprint and compatible polarity.
- `related`: semantic neighborhood is shared, but identity is not proven. This class never authorizes automatic merge.
- `conflict`: high semantic overlap with opposing polarity and sufficient confidence.
- `distinct`: evidence is insufficient for identity, relation, or conflict.

## Controlled probes
The implemented tests cover:
1. identical fingerprint across different modalities -> `same`;
2. cup/handle/ceramic contexts with differing attributes -> `related`;
3. same semantic descriptor with opposing polarity -> `conflict`;
4. low-confidence disagreement -> not forced into `conflict`;
5. unrelated finance/database descriptors -> `distinct`.

An initial `related` threshold was too conservative for 3-of-5 shared semantic tokens (Jaccard 0.60). The combined-score cutoff was reduced from 0.45 to 0.40. This does not enable automatic merging because `related` remains explicitly non-destructive.

## Interpretation
The consensus layer is deliberately asymmetric in risk: false identity is treated as more dangerous than missed relation. Shared knowledge may therefore remain separate until stronger identity evidence appears.

This behavior is appropriate for distributed agents/humanoids where independent observations can be correlated, complementary, stale, or contradictory.

## Status
v0.89 is an experimental consensus mechanism. Thresholds remain subject to broader semantic datasets and adversarial tests before v1.0.
