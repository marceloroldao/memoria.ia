from __future__ import annotations

import importlib.util
import sys
from collections import Counter, defaultdict
from pathlib import Path

from memoria_resolutiva.two_channel_v96 import EntityStateTwoChannelRouterV96

_HERE = Path(__file__).resolve().parent
_ADV = _HERE / "adversarial_generalization_v96.py"
_spec = importlib.util.spec_from_file_location("adversarial_generalization_v96_two_channel", _ADV)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load adversarial dataset: {_ADV}")
_adv = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _adv
_spec.loader.exec_module(_adv)
TRAIN = _adv.TRAIN
ADVERSARIAL = _adv.ADVERSARIAL
COUNTEREXAMPLES = _adv.COUNTEREXAMPLES


def build(min_state_score: float = 0.12):
    router = EntityStateTwoChannelRouterV96(
        threshold=0.07,
        min_margin=0.0,
        negative_threshold=0.20,
        min_contrast_margin=0.04,
        min_state_score=min_state_score,
        min_state_terms=1,
    )
    for concept_id, examples in TRAIN.items():
        router.observe_concept(concept_id, examples)
    for concept_id, examples in COUNTEREXAMPLES.items():
        for sentence in examples:
            router.observe_counterexample(concept_id, sentence)
    return router


def evaluate(router):
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    positive = positive_ok = false_positive = wrong_known = abstained = 0
    errors = Counter()
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
            errors[kind] += 1
            print({
                "kind": kind,
                "expected": expected,
                "predicted": predicted,
                "source": result.source,
                "lexical_score": result.lexical_score,
                "entity_score": result.entity_score,
                "state_score": result.state_score,
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
        "known_recall": positive_ok / positive,
        "open_set_false_positive_rate": false_positive / negatives,
        "wrong_known_class_rate": wrong_known / positive,
        "known_abstention_rate": abstained / positive,
        "errors_by_kind": dict(errors),
    }
    return metrics, matrix


def main():
    metrics, matrix = evaluate(build())
    print("two_channel_adversarial_v96")
    print(metrics)
    print("confusion_matrix")
    for expected in sorted(matrix):
        print(expected, dict(matrix[expected]))


if __name__ == "__main__":
    main()
