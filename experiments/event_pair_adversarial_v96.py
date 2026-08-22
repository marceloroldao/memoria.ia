from __future__ import annotations

import importlib.util
import sys
from collections import Counter, defaultdict
from pathlib import Path

from memoria_resolutiva.event_pair_v96 import EventPairTrajectoryRouterV96

_HERE = Path(__file__).resolve().parent


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_split = _load_module("natural_language_split_v96_event_pair", _HERE / "natural_language_split_v96.py")
_adv = _load_module("adversarial_generalization_v96_event_pair", _HERE / "adversarial_generalization_v96.py")

TRAIN = _split.TRAIN
CONTRASTIVE_CALIBRATION = _split.CONTRASTIVE_CALIBRATION
ADVERSARIAL = _adv.ADVERSARIAL


def build(
    *,
    min_state_score: float = 0.08,
    min_event_pairs: int = 1,
    strong_state_score: float = 0.30,
) -> EventPairTrajectoryRouterV96:
    router = EventPairTrajectoryRouterV96(
        threshold=0.07,
        min_state_score=min_state_score,
        min_event_pairs=min_event_pairs,
        strong_state_score=strong_state_score,
    )
    for concept_id, examples in TRAIN.items():
        router.observe_concept(concept_id, examples)
    # Calibration-only negatives; the frozen ADVERSARIAL rows are never learned.
    for concept_id, examples in CONTRASTIVE_CALIBRATION.items():
        for sentence in examples:
            router.observe_counterexample(concept_id, sentence)
    return router


def evaluate(router: EventPairTrajectoryRouterV96, *, verbose: bool = True) -> dict[str, float | int | dict[str, int]]:
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
                    "lexical_score": result.lexical_score,
                    "state_score": result.state_score,
                    "positive_pair_hits": result.positive_pair_hits,
                    "ambiguous_pair_hits": result.ambiguous_pair_hits,
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
    if verbose:
        print("event_pair_adversarial_v96")
        print(metrics)
        print("confusion_matrix")
        for expected in sorted(matrix):
            print(expected, dict(matrix[expected]))
    return metrics


def main() -> None:
    router = build()
    metrics = evaluate(router, verbose=True)
    # Deliberately loose research gate: the benchmark is intended to expose
    # weaknesses, not encode the desired result into CI.
    if metrics["known_recall"] < 0.40:
        raise SystemExit("known recall collapsed below 0.40")
    if metrics["wrong_known_class_rate"] > 0.35:
        raise SystemExit("wrong-known-class rate exceeded 0.35")


if __name__ == "__main__":
    main()
