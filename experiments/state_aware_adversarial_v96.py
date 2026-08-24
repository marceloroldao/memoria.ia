from __future__ import annotations

import importlib.util
import sys
from collections import Counter, defaultdict
from pathlib import Path

from memoria_resolutiva.state_aware_semantic_v96 import StateAwareTrajectoryContrastiveRouterV96

_HERE = Path(__file__).resolve().parent
_ADV_PATH = _HERE / "adversarial_generalization_v96.py"
_spec = importlib.util.spec_from_file_location("adversarial_generalization_v96_data", _ADV_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load adversarial dataset: {_ADV_PATH}")
_adv = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _adv
_spec.loader.exec_module(_adv)
TRAIN = _adv.TRAIN
ADVERSARIAL = _adv.ADVERSARIAL
COUNTEREXAMPLES = _adv.COUNTEREXAMPLES


def build() -> StateAwareTrajectoryContrastiveRouterV96:
    router = StateAwareTrajectoryContrastiveRouterV96(
        threshold=0.12,
        min_margin=0.02,
        negative_threshold=0.20,
        min_contrast_margin=0.04,
    )
    for concept_id, examples in TRAIN.items():
        router.observe_concept(concept_id, examples)
    for concept_id, examples in COUNTEREXAMPLES.items():
        for sentence in examples:
            router.observe_counterexample(concept_id, sentence)
    return router


def main() -> None:
    router = build()
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    positive = positive_ok = false_positive = wrong_known = abstained = 0
    errors_by_kind: Counter[str] = Counter()

    for expected, sentence in ADVERSARIAL:
        result = router.resolve(sentence)
        predicted = result.concept_id
        matrix[str(expected)][str(predicted)] += 1
        if expected is None:
            false_positive += int(predicted is not None)
        else:
            positive += 1
            positive_ok += int(predicted == expected)
            wrong_known += int(predicted is not None and predicted != expected)
            abstained += int(predicted is None)
        if predicted != expected:
            kind = "open_set_fp" if expected is None else ("known_abstention" if predicted is None else "wrong_known")
            errors_by_kind[kind] += 1
            print({
                "kind": kind,
                "expected": expected,
                "predicted": predicted,
                "source": result.source,
                "positive_score": result.positive_score,
                "negative_score": result.negative_score,
                "contrast_margin": result.contrast_margin,
                "sentence": sentence,
            })

    negatives = sum(1 for expected, _ in ADVERSARIAL if expected is None)
    n = len(ADVERSARIAL)
    correct = sum(matrix[k][k] for k in matrix)
    metrics = {
        "n": n,
        "known_queries": positive,
        "open_set_queries": negatives,
        "accuracy": correct / n,
        "known_recall": positive_ok / positive if positive else 0.0,
        "open_set_false_positive_rate": false_positive / negatives if negatives else 0.0,
        "wrong_known_class_rate": wrong_known / positive if positive else 0.0,
        "known_abstention_rate": abstained / positive if positive else 0.0,
        "errors_by_kind": dict(errors_by_kind),
    }
    print("state_aware_adversarial_v96")
    print(metrics)
    print("confusion_matrix")
    for expected in sorted(matrix):
        print(expected, dict(matrix[expected]))


if __name__ == "__main__":
    main()
