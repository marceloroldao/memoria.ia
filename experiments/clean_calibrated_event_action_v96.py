from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from memoria_resolutiva.reranked_event_action_v96 import RerankedEventActionRouterV96

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_protocol = _load("v096_training_protocol_clean_selector", _HERE / "v096_training_protocol.py")


@dataclass(frozen=True, slots=True)
class Metrics:
    accuracy: float
    known_recall: float
    false_positive_rate: float
    wrong_known_class_rate: float
    known_abstention_rate: float


def build(*, retrieval_threshold: float, min_margin: float, event_score: float):
    # Negative reranking is deliberately disabled (lambda=0): prior development
    # experiments showed that concept-negative penalization worsened known-class
    # identity. The clean action corpus is still used by the independent event gate.
    router = RerankedEventActionRouterV96(
        retrieval_threshold=retrieval_threshold,
        rerank_lambda=0.0,
        min_reranked_score=0.0,
        min_reranked_margin=min_margin,
        min_event_action_score=event_score,
    )
    for concept_id, examples in _protocol.TRAIN.items():
        router.observe_concept(concept_id, examples)
    for sentence in _protocol.iter_clean_global_actions():
        router.observe_action(sentence)
    return router


def evaluate(router, rows):
    rows = list(rows)
    correct = known = known_ok = fp = wrong = abstained = 0
    negatives = sum(1 for expected, _ in rows if expected is None)
    for expected, sentence in rows:
        predicted = router.resolve(sentence).concept_id
        correct += int(predicted == expected)
        if expected is None:
            fp += int(predicted is not None)
        else:
            known += 1
            known_ok += int(predicted == expected)
            wrong += int(predicted is not None and predicted != expected)
            abstained += int(predicted is None)
    return Metrics(
        accuracy=correct / len(rows) if rows else 0.0,
        known_recall=known_ok / known if known else 0.0,
        false_positive_rate=fp / negatives if negatives else 0.0,
        wrong_known_class_rate=wrong / known if known else 0.0,
        known_abstention_rate=abstained / known if known else 0.0,
    )


def calibrate():
    rows = _protocol.clean_calibration_rows()
    best = None
    for retrieval_i in range(4, 16):
        retrieval_threshold = retrieval_i / 100
        for margin_i in range(0, 51, 5):
            min_margin = margin_i / 1000
            for event_i in range(-50, 21, 5):
                event_score = event_i / 100
                router = build(
                    retrieval_threshold=retrieval_threshold,
                    min_margin=min_margin,
                    event_score=event_score,
                )
                metrics = evaluate(router, rows)
                # Conservative selection: errors on unseen/open actions and wrong
                # known classes are penalized more strongly than abstention.
                objective = (
                    metrics.accuracy
                    - 0.75 * metrics.false_positive_rate
                    - 1.00 * metrics.wrong_known_class_rate
                )
                candidate = (
                    objective,
                    metrics.accuracy,
                    metrics.known_recall,
                    -metrics.false_positive_rate,
                    -metrics.wrong_known_class_rate,
                    -retrieval_threshold,
                    -min_margin,
                    -event_score,
                    retrieval_threshold,
                    min_margin,
                    event_score,
                    metrics,
                )
                if best is None or candidate[:-1] > best[:-1]:
                    best = candidate
    assert best is not None
    return best[-4], best[-3], best[-2], best[-1]


def main() -> None:
    audit = _protocol.protocol_audit()
    if not audit["clean_training_path_exactly_disjoint_from_test"]:
        raise SystemExit("clean calibration path overlaps TEST")

    retrieval_threshold, min_margin, event_score, calibration_metrics = calibrate()
    selected = build(
        retrieval_threshold=retrieval_threshold,
        min_margin=min_margin,
        event_score=event_score,
    )
    test_metrics = evaluate(selected, _protocol.TEST)

    print("clean_calibrated_event_action_v96")
    print(audit)
    print({
        "selection_protocol": _protocol.CLEAN_PROTOCOL_ID,
        "retrieval_threshold": retrieval_threshold,
        "min_top1_top2_margin": min_margin,
        "min_event_action_score": event_score,
        "calibration_metrics": calibration_metrics,
        "test_metrics": test_metrics,
        "publication_note": (
            "TEST is exact-disjoint from the clean training path but has been inspected "
            "during prior development; treat this as validation, not a fresh blind holdout."
        ),
    })


if __name__ == "__main__":
    main()
