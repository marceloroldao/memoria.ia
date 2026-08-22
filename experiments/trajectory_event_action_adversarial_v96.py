from __future__ import annotations

import importlib.util
import sys
from collections import Counter, defaultdict
from pathlib import Path

from memoria_resolutiva.trajectory_event_action_v96 import TrajectoryEventActionRouterV96

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_split = _load("natural_language_split_v96_traj_event", _HERE / "natural_language_split_v96.py")
_adv = _load("adversarial_generalization_v96_traj_event", _HERE / "adversarial_generalization_v96.py")
TRAIN = _split.TRAIN
CALIBRATION = _split.CALIBRATION
CONTRASTIVE_CALIBRATION = _split.CONTRASTIVE_CALIBRATION
ADVERSARIAL = _adv.ADVERSARIAL
COUNTEREXAMPLES = _adv.COUNTEREXAMPLES


def build(*, min_event_action_score: float = -0.20):
    router = TrajectoryEventActionRouterV96(min_event_action_score=min_event_action_score)
    for concept_id, examples in TRAIN.items():
        router.observe_concept(concept_id, examples)

    # Preserve concept-specific negative trajectories used by the adversarial baseline.
    for concept_id, examples in COUNTEREXAMPLES.items():
        for sentence in examples:
            router.observe_counterexample(concept_id, sentence)

    # Additional calibration negatives feed only the global event/action channel.
    for expected, sentence in CALIBRATION:
        if expected is None:
            router.observe_action(sentence)
    for concept_id, examples in CONTRASTIVE_CALIBRATION.items():
        if concept_id in COUNTEREXAMPLES:
            # Avoid duplicating concept-specific negative trajectory; still add action evidence.
            for sentence in examples:
                router.observe_action(sentence)
        else:
            for sentence in examples:
                router.observe_counterexample(concept_id, sentence)
    return router


def evaluate(router, *, verbose: bool = True):
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    known = known_ok = fp = wrong = abstained = correct = 0
    errors = Counter()
    negatives = sum(1 for expected, _ in ADVERSARIAL if expected is None)

    for expected, sentence in ADVERSARIAL:
        result = router.resolve(sentence)
        predicted = result.concept_id
        matrix[str(expected)][str(predicted)] += 1
        correct += int(predicted == expected)
        if expected is None:
            fp += int(predicted is not None)
        else:
            known += 1
            known_ok += int(predicted == expected)
            wrong += int(predicted is not None and predicted != expected)
            abstained += int(predicted is None)

        if predicted != expected:
            kind = "open_set_fp" if expected is None else ("known_abstention" if predicted is None else "wrong_known")
            errors[kind] += 1
            if verbose:
                print({
                    "kind": kind,
                    "expected": expected,
                    "predicted": predicted,
                    "source": result.source,
                    "positive_score": result.positive_score,
                    "negative_score": result.negative_score,
                    "contrast_margin": result.contrast_margin,
                    "event_action_score": result.event_action_score,
                    "sentence": sentence,
                })

    metrics = {
        "n": len(ADVERSARIAL),
        "known_queries": known,
        "open_set_queries": negatives,
        "accuracy": correct / len(ADVERSARIAL),
        "known_recall": known_ok / known,
        "open_set_false_positive_rate": fp / negatives,
        "wrong_known_class_rate": wrong / known,
        "known_abstention_rate": abstained / known,
        "errors_by_kind": dict(errors),
    }
    if verbose:
        print("trajectory_event_action_adversarial_v96")
        print(metrics)
        print("confusion_matrix")
        for expected in sorted(matrix):
            print(expected, dict(matrix[expected]))
    return metrics


def main() -> None:
    evaluate(build(), verbose=True)


if __name__ == "__main__":
    main()
