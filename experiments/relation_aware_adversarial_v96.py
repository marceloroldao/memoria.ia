from __future__ import annotations

import importlib.util
import sys
from collections import Counter, defaultdict
from pathlib import Path

from memoria_resolutiva.relation_aware_v96 import RelationAwareTrajectoryRouterV96

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_split = _load("natural_language_split_v96_relation", _HERE / "natural_language_split_v96.py")
_adv = _load("adversarial_generalization_v96_relation", _HERE / "adversarial_generalization_v96.py")
TRAIN = _split.TRAIN
ADVERSARIAL = _adv.ADVERSARIAL
COUNTEREXAMPLES = _adv.COUNTEREXAMPLES


def build(threshold: float = 0.08) -> RelationAwareTrajectoryRouterV96:
    router = RelationAwareTrajectoryRouterV96(
        threshold=threshold,
        min_margin=0.0,
        negative_threshold=0.20,
        min_contrast_margin=0.04,
        negation_scope=3,
    )
    for concept_id, examples in TRAIN.items():
        router.observe_concept(concept_id, examples)
    for concept_id, examples in COUNTEREXAMPLES.items():
        for sentence in examples:
            router.observe_counterexample(concept_id, sentence)
    return router


def evaluate(threshold: float = 0.08, *, verbose: bool = True):
    router = build(threshold)
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
            if verbose:
                print({
                    "kind": kind,
                    "expected": expected,
                    "predicted": predicted,
                    "source": result.source,
                    "positive_score": result.positive_score,
                    "negative_score": result.negative_score,
                    "contrast_margin": result.contrast_margin,
                    "rejected_by_negation": result.rejected_by_negation,
                    "sentence": sentence,
                })

    negatives = sum(1 for expected, _ in ADVERSARIAL if expected is None)
    n = len(ADVERSARIAL)
    correct = sum(matrix[k][k] for k in matrix)
    metrics = {
        "threshold": threshold,
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
    return metrics, matrix


def main() -> None:
    metrics, matrix = evaluate(0.08, verbose=True)
    print("relation_aware_adversarial_v96")
    print(metrics)
    print("confusion_matrix")
    for expected in sorted(matrix):
        print(expected, dict(matrix[expected]))


if __name__ == "__main__":
    main()
