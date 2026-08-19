# v0.96 adversarial generalization results

## Status

Project-controlled GitHub Actions experiment. This document records a negative/limiting result and must not be read as a production benchmark.

## Independent adversarial corpus

A new corpus was written separately from the earlier held-out benchmark. It contains 64 queries:

- 48 known-class queries across 8 concepts;
- 16 difficult open-set / near-miss queries;
- paraphrases, short phrases, typos, negation, neighboring concepts and same-entity/different-state cases.

At the previously strong operating point (`threshold=0.12`) the trajectory-contrastive sentence router produced:

- accuracy: **0.640625**;
- known recall: **0.666667**;
- open-set false-positive rate: **0.4375**;
- wrong-known-class rate: **0.041667**;
- known abstention rate: **0.291667**.

This breaks the earlier 100% result on the smaller held-out corpus and demonstrates that the prior result did not generalize to harder language.

## Error diagnosis

Three failure families dominate:

1. **Sparse/short paraphrases**: valid queries often score below the positive threshold.
2. **Negation/state loss**: bag-of-words can confuse statements such as `fibra nao rompeu` with `fiber_break`.
3. **Same entity, different event**: terms such as `roteador`, `fibra`, `conta` or `potencia optica` can attract a known class even when the event/state is different.

## State-aware experiment

An experimental sparse representation added adjacent content bigrams and local negation markers. At threshold 0.12 it produced:

- accuracy: **0.546875**;
- known recall: **0.416667**;
- open-set false-positive rate: **0.0625**;
- wrong-known-class rate: **0.020833**;
- known abstention rate: **0.5625**.

Thus state-aware features strongly reduced open-set false positives, but diluted positive scores and caused excessive abstention.

An exploratory threshold sweep (0.03-0.12) showed no simple operating point that simultaneously recovered high recall and retained the low open-set FP rate. For example:

- threshold 0.04: accuracy 0.71875, known recall 0.791667, open-set FP 0.50;
- threshold 0.08: accuracy 0.671875, known recall 0.666667, open-set FP 0.3125;
- threshold 0.11: accuracy 0.5625, known recall 0.4375, open-set FP 0.0625.

Therefore the state-aware feature expansion is retained as an experimental negative/trade-off result and is **not promoted to default**.

## Scientific conclusion

The new bottleneck is not candidate count or a single global threshold. The system needs a better representation of **event/state relations and novelty**, while preserving high recall for short paraphrases. The adversarial corpus is now a required regression benchmark for future v0.96 semantic-routing changes.
