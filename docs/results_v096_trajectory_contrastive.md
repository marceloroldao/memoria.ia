# v0.96 Trajectory-Level Contrastive Memory

## Motivation

The aggregated negative-profile experiment reduced open-set false positives but also reduced known-class recall. The failure mode was overgeneralization: unrelated counterexamples were compressed into one broad negative prototype per concept.

## New experiment

`TrajectoryContrastiveRouterV96` stores each counterexample as an independent negative trajectory rather than merging them.

For a winning positive concept K:

- compute the ordinary positive sentence score;
- compare the query only against negative trajectories attached to K;
- use the strongest local negative match;
- reject only when that local negative match is strong enough and the positive-vs-negative contrast margin is too small.

This preserves the separation between knowledge identity and trajectory evidence.

## Reproduction

From a clean checkout of branch `experiment/v0.96-semantic-routing`:

```bash
python -m pip install -e .
python -m pytest -q tests/test_trajectory_contrastive_v96.py
python experiments/trajectory_contrastive_split_v96.py
```

The benchmark prints:

- overall accuracy;
- known-class recall;
- open-set false-positive rate;
- wrong-known-class rate;
- known-query abstention rate;
- confusion matrix;
- details for every error/rejection.

## Promotion rule

This mechanism must not become default unless a clean run demonstrates that it improves open-set rejection relative to the base sentence router while preserving known-class recall close to the base benchmark. The published v0.95.1 baseline remains unchanged.
