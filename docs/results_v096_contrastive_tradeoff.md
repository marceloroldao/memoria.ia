# v0.96 Contrastive Open-Set Trade-off

A calibrated contrastive gate was evaluated after scalar novelty diagnostics failed to separate hard open-set negatives from valid short positive queries.

## Reconstructed equivalent-local result

Using the split benchmark and calibration-only counterexamples, the contrastive margin selected by calibration removed the hard open-set false positives in the reconstructed equivalent-local evaluation, but at a substantial recall cost.

Approximate reconstructed comparison:

| mode | known recall | open-set false-positive rate | wrong-known-class rate |
|---|---:|---:|---:|
| sentence sparse baseline | 100% in this reconstruction | 37.5% | 0% |
| contrastive calibrated | 83.3% | 0% | 0% |

The exact figures must be reproduced from a clean repository checkout before any release claim.

## Interpretation

The contrastive profile learns useful negative evidence, but a single aggregated negative prototype can over-generalize. For example, counterexamples describing completed payments share enough vocabulary with genuine overdue-payment queries to suppress valid `payment_delay` memories. Likewise, ONU maintenance counterexamples can suppress genuine optical-loss queries because both legitimately contain `onu` and optical vocabulary.

Therefore the current contrastive gate is **not promoted to default**.

The result suggests that future work should preserve counterexamples as separate trajectories or local negative exemplars rather than collapsing them into one aggregate negative bag-of-words profile. A local/exemplar decision could reject only when a query is close to a specific counterexample while retaining positive evidence from the concept prototype.

This negative result is retained as part of the v0.96 scientific record.
