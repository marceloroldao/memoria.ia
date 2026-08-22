from __future__ import annotations

import importlib.util
import sys
from collections import Counter, defaultdict
from pathlib import Path

from memoria_resolutiva.soft_state_v96 import SoftStateEvidenceRouterV96

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_split = _load("natural_language_split_v96_soft_state", _HERE / "natural_language_split_v96.py")
_adv = _load("adversarial_generalization_v96_soft_state", _HERE / "adversarial_generalization_v96.py")
TRAIN = _split.TRAIN
CONTRASTIVE_CALIBRATION = _split.CONTRASTIVE_CALIBRATION
ADVERSARIAL = _adv.ADVERSARIAL


def build(*, min_soft_similarity: float = 0.30, min_total_state_evidence: int = 1):
    router = SoftStateEvidenceRouterV96(
        threshold=0.07,
        min_soft_similarity=min_soft_similarity,
        min_total_state_evidence=min_total_state_evidence,
    )
    for concept_id, examples in TRAIN.items():
        router.observe_concept(concept_id, examples)
    for concept_id, examples in CONTRASTIVE_CALIBRATION.items():
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
                    "lexical_score": result.lexical_score,
                    "exact_state_hits": result.exact_state_hits,
                    "soft_state_hits": result.soft_state_hits,
                    "best_soft_similarity": result.best_soft_similarity,
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
        print("soft_state_adversarial_v96")
        print(metrics)
        print("confusion_matrix")
        for expected in sorted(matrix):
            print(expected, dict(matrix[expected]))
    return metrics


def main() -> None:
    evaluate(build(), verbose=True)


if __name__ == "__main__":
    main()
