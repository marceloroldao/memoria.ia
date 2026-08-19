from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from memoria_resolutiva.state_aware_semantic_v96 import StateAwareTrajectoryContrastiveRouterV96

_HERE = Path(__file__).resolve().parent
_ADV_PATH = _HERE / "adversarial_generalization_v96.py"
_spec = importlib.util.spec_from_file_location("adversarial_generalization_v96_sweep", _ADV_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load adversarial dataset: {_ADV_PATH}")
_adv = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _adv
_spec.loader.exec_module(_adv)
TRAIN = _adv.TRAIN
ADVERSARIAL = _adv.ADVERSARIAL
COUNTEREXAMPLES = _adv.COUNTEREXAMPLES


def evaluate(threshold: float) -> dict[str, float]:
    router = StateAwareTrajectoryContrastiveRouterV96(
        threshold=threshold,
        min_margin=0.02,
        negative_threshold=0.20,
        min_contrast_margin=0.04,
    )
    for concept_id, examples in TRAIN.items():
        router.observe_concept(concept_id, examples)
    for concept_id, examples in COUNTEREXAMPLES.items():
        for sentence in examples:
            router.observe_counterexample(concept_id, sentence)

    correct = positive = positive_ok = false_positive = wrong_known = abstained = 0
    negatives = 0
    for expected, sentence in ADVERSARIAL:
        predicted = router.resolve(sentence).concept_id
        correct += int(predicted == expected)
        if expected is None:
            negatives += 1
            false_positive += int(predicted is not None)
        else:
            positive += 1
            positive_ok += int(predicted == expected)
            wrong_known += int(predicted is not None and predicted != expected)
            abstained += int(predicted is None)

    n = len(ADVERSARIAL)
    return {
        "threshold": threshold,
        "accuracy": correct / n,
        "known_recall": positive_ok / positive,
        "open_set_false_positive_rate": false_positive / negatives,
        "wrong_known_class_rate": wrong_known / positive,
        "known_abstention_rate": abstained / positive,
    }


def main() -> None:
    # Exploratory only: this sweep uses the adversarial corpus and therefore must
    # not be treated as a held-out estimate after selecting an operating point.
    for threshold in (0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12):
        print(evaluate(threshold))


if __name__ == "__main__":
    main()
