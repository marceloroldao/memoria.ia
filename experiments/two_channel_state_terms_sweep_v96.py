from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

from memoria_resolutiva.two_channel_v96 import EntityStateTwoChannelRouterV96

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_split = _load("natural_language_split_v96_state_terms", _HERE / "natural_language_split_v96.py")
_adv = _load("adversarial_generalization_v96_state_terms", _HERE / "adversarial_generalization_v96.py")
TRAIN = _split.TRAIN
CONTRASTIVE_CALIBRATION = _split.CONTRASTIVE_CALIBRATION
ADVERSARIAL = _adv.ADVERSARIAL


def evaluate(min_state_terms: int, min_state_score: float) -> dict:
    router = EntityStateTwoChannelRouterV96(
        threshold=0.07,
        min_margin=0.0,
        min_state_score=min_state_score,
        min_state_terms=min_state_terms,
    )
    for concept_id, examples in TRAIN.items():
        router.observe_concept(concept_id, examples)
    for concept_id, examples in CONTRASTIVE_CALIBRATION.items():
        for sentence in examples:
            router.observe_counterexample(concept_id, sentence)

    known = known_ok = fp = wrong = abstained = correct = 0
    errors = Counter()
    negatives = sum(1 for expected, _ in ADVERSARIAL if expected is None)

    for expected, sentence in ADVERSARIAL:
        predicted = router.resolve(sentence).concept_id
        correct += int(predicted == expected)
        if expected is None:
            fp += int(predicted is not None)
            if predicted is not None:
                errors["open_set_fp"] += 1
        else:
            known += 1
            known_ok += int(predicted == expected)
            wrong += int(predicted is not None and predicted != expected)
            abstained += int(predicted is None)
            if predicted is None:
                errors["known_abstention"] += 1
            elif predicted != expected:
                errors["wrong_known"] += 1

    return {
        "min_state_terms": min_state_terms,
        "min_state_score": min_state_score,
        "accuracy": correct / len(ADVERSARIAL),
        "known_recall": known_ok / known,
        "open_set_false_positive_rate": fp / negatives,
        "wrong_known_class_rate": wrong / known,
        "known_abstention_rate": abstained / known,
        "errors_by_kind": dict(errors),
    }


def main() -> None:
    for min_state_terms in (1, 2, 3):
        for min_state_score in (0.04, 0.06, 0.08, 0.10, 0.12):
            print(evaluate(min_state_terms, min_state_score))


if __name__ == "__main__":
    main()
