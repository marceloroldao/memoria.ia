# v0.96 relation-aware threshold sweep

The relation-aware event/state router was evaluated on the frozen 64-query adversarial development set across thresholds 0.04-0.12.

Best observed overall accuracy occurred at thresholds 0.07 and 0.08:

- accuracy: 0.71875;
- known recall: 0.75;
- open-set false-positive rate: 0.375;
- wrong-known-class rate: 0.0625;
- known abstention rate: 0.1875.

Lowering the threshold to 0.04 increased known recall to 0.770833 but raised open-set false positives to 0.5625. Raising the threshold to 0.11 removed wrong-known-class errors but did not reduce open-set false positives below 0.375 and increased abstention.

Conclusion: threshold tuning alone cannot solve the remaining error pattern. The dominant residual problem is entity-only/entity-heavy evidence without sufficient event/state evidence. The next experiment should separate entity evidence from state/event evidence rather than continue threshold optimization.
