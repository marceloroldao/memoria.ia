# Memoria.ia v0.96 — Fresh Holdout Protocol

Status: **experimental / preregistered before fresh holdout evaluation**

Protocol compatibility: this document applies to the experimental `v0.96-semantic-routing` line and does not supersede the stable project specification.

## Purpose

This protocol defines the evaluation procedure that must be frozen before a new holdout corpus is introduced. Its purpose is to prevent test-set tuning and to distinguish development diagnostics from evidence of generalization.

## Frozen architecture

The current candidate family separates three decisions:

1. sparse concept retrieval from positive concept memory;
2. ambiguity control using the top-1 versus top-2 concept score margin;
3. an independent sparse event-versus-action/normality gate.

Negative concept reranking is fixed to `lambda = 0` for this protocol because development experiments showed that increasing the negative reranking penalty worsened known-class identity errors.

No embedding model or neural network is used by this experimental router.

## Parameter selection

Parameters may be selected only from the clean calibration path defined in:

- `experiments/v096_training_protocol.py`
- protocol ID `v0.96-clean-calibration-protocol-2`

The selector may tune only:

- sparse retrieval threshold;
- top-1/top-2 ambiguity margin;
- event-versus-action acceptance threshold.

The `TEST` split, the 64-sentence adversarial development corpus, and `DEVELOPMENT_COUNTEREXAMPLES` must not participate in parameter selection.

## Development-only corpora

The following material has already been inspected while architectures were being changed and therefore is **not a blind publication holdout**:

- the existing `TEST` split;
- `ADVERSARIAL_DEV` from `adversarial_generalization_v96.py`;
- `DEVELOPMENT_COUNTEREXAMPLES` from the same development file.

These datasets remain valuable for regression and diagnostic analysis, but their metrics must be labelled validation/development metrics.

## Fresh holdout requirements

A publication-grade holdout should be supplied or collected only after the architecture and calibration selector are frozen. Prefer externally sourced or operationally collected samples over assistant-generated paraphrases.

The fresh holdout must:

- contain known-class paraphrases not present in training/calibration;
- contain open-set actions, normal states, adjacent topics, and benign entity mentions;
- include difficult class-boundary cases;
- be stored with stable identifiers and a content fingerprint before the first evaluation;
- remain excluded from all training, calibration, threshold selection, vocabulary construction, and architecture changes.

If the architecture or thresholds are changed after viewing fresh-holdout results, that corpus becomes a development set and a new untouched holdout is required.

## Primary metrics

Report at minimum:

- accuracy;
- known-class recall;
- open-set false-positive rate;
- wrong-known-class rate;
- known-class abstention rate;
- confusion matrix and sample counts.

All metric denominators must be reported.

## Decision rule

The fresh holdout is evaluated once with the frozen calibration-selected configuration. No threshold is chosen from holdout performance.

A release/publication decision requires, in addition to acceptable holdout behavior:

- reproducible CI;
- documented methodology and negative results;
- licensing audit;
- compatibility declaration with the applicable Resolutive specification;
- final README/documentation review;
- release metadata suitable for GitHub and Zenodo.

## Scientific interpretation

A positive fresh-holdout result would support the claim that the sparse non-neural event/action separation generalizes beyond the development corpora. It would not by itself establish equivalence or superiority to modern neural language models; external baselines and larger datasets would still be required.
