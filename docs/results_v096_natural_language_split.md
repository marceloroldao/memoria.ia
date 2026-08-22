# v0.96 Natural-Language Train/Calibration/Test Benchmark

This experiment moves beyond the earlier controlled synonym corpora and uses explicit, textually disjoint training, calibration and test splits.

## Structure

- 8 known concepts;
- 4 training sentences per concept;
- calibration set containing known concepts and open-set negatives;
- independent test set with 24 positive queries and 8 open-set negatives;
- sentence-level sparse, non-neural representation;
- threshold and margin chosen on calibration only;
- confusion matrix and error taxonomy reported on test only.

The split and calibration procedure are reproducible in:

```bash
python experiments/natural_language_split_v96.py
```

## Equivalent local result

An equivalent local execution of the current experiment produced approximately:

- overall accuracy: **29/32 = 90.6%**;
- known-class recall: **23/24 = 95.8%**;
- wrong-known-class predictions: **0/32**;
- known-query abstentions: **1/32**;
- open-set false positives: **2/32** overall, or **2/8** among negative queries.

The remaining known-query miss was an abstention rather than an incorrect known-class assignment.

Two open-set negatives exposed the main current weakness:

1. a power-supply replacement mentioning `onu` was attracted toward `optical_loss`;
2. a payment receipt mentioning `pagamento` was attracted toward `payment_delay`.

These are not candidate-pruning failures. They are **open-set novelty failures** caused by a small number of high-overlap lexical features.

## Interpretation

The v0.96 research direction has shifted:

1. token-level routing was insufficient on natural language (~60% in the first small noisy experiment);
2. sentence-level sparse profiles improved the same line of testing (~80% in the initial small sample);
3. proper split/calibration/test evaluation reached ~90.6% in the current equivalent local benchmark;
4. the dominant remaining problem is rejecting semantically related but out-of-scope events.

Therefore the next optimization should not primarily increase candidate count. It should add a conservative **novelty/evidence sufficiency gate** before accepting a known concept.

## Scientific status

These are small project-controlled Portuguese-language examples, not an external benchmark and not a claim of general natural-language understanding. Results must be re-run from a clean checkout before any release decision. The published v0.95.1 baseline remains unchanged.
