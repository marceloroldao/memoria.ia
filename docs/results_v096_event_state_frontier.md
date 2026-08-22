# v0.96 — Event/state generalization frontier

## Purpose

This note records negative and mixed results from attempts to improve non-neural event/state recognition on the frozen 64-row adversarial corpus (48 known, 16 open-set). The adversarial rows are never reused as training or counterexamples.

## Reference points

- Contrastive sentence baseline (`threshold=0.12`): accuracy 0.640625, known recall 0.6667, open-set FP 0.4375.
- Relation-aware router: accuracy 0.71875, known recall 0.75, open-set FP 0.375.
- Entity/state two-channel router: best conservative region around `min_state_score=0.10–0.12`, with open-set FP 0.25 and known recall about 0.67–0.69.

## Exact event-pair experiment — negative result

Requiring exact unordered lexical pairs learned from positive examples strongly rejected open-set inputs but failed to generalize to paraphrases:

- accuracy: 0.421875
- known recall: 0.229167
- open-set FP: 0.0
- wrong-known: 0.0
- known abstention: 0.770833

Interpretation: exact word-pair trajectories are too brittle for natural-language paraphrase. Most valid adversarial paraphrases share no exact positive pair with training.

## Exact state-term multiplicity — negative trade-off

Using the existing two-channel model:

- 1 state term, score 0.10: accuracy 0.6875, recall 0.645833, open-set FP 0.1875.
- 2 state terms: accuracy 0.421875, recall 0.25, open-set FP 0.0625.
- 3 state terms: accuracy 0.28125, recall 0.041667, open-set FP 0.0.

Interpretation: simply demanding more exact discriminative terms is another conservative rejection mechanism, not a generalization mechanism.

## Contextual soft-state experiment — mixed/negative result

`SoftStateEvidenceRouterV96` uses the existing sparse `TextContextMemory` to accept state terms through contextual neighborhood similarity, learned only from TRAIN and calibration examples.

Best one-evidence region (`min_soft_similarity` 0.15–0.35):

- accuracy: 0.703125
- known recall: 0.708333
- open-set FP: 0.3125
- wrong-known: 0.083333
- known abstention: 0.208333

At `min_soft_similarity=0.50`:

- accuracy: 0.6875
- known recall: 0.666667
- open-set FP: 0.25

With two total state evidences and similarity 0.35:

- accuracy: 0.578125
- known recall: 0.50
- open-set FP: 0.1875
- wrong-known: 0.020833

Interpretation: contextual similarity recovers some paraphrase support, but it also transfers support to related non-events/actions. It therefore does not solve the core distinction between **entity-related action** and **fault/event state**.

## Current scientific conclusion

The current frontier is not candidate search, threshold calibration, exact term multiplicity, or local contextual similarity. The unresolved problem is relational polarity between:

1. entity/topic;
2. action/maintenance/administrative operation;
3. fault/event state;
4. negated or normal state.

The next experiments should learn a contrastive event-vs-action boundary from training/calibration trajectories without using the frozen adversarial corpus. This should remain sparse/deterministic unless evidence demonstrates that a neural fallback is required.

No result in this note is a claim of general language understanding. All metrics are project-controlled research measurements from GitHub Actions and must remain reproducible before any release claim.
