from __future__ import annotations

import importlib.util
import sys
from collections import Counter, defaultdict
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


_protocol = _load("v096_training_protocol_reranked_event", _HERE / "v096_training_protocol.py")
TRAIN = _protocol.TRAIN
ADVERSARIAL = _protocol.ADVERSARIAL
PROTOCOL_ID = _protocol.PROTOCOL_ID


def build(
    *,
    retrieval_threshold: float = 0.07,
    rerank_lambda: float = 0.5,
    min_reranked_score: float = 0.02,
    min_reranked_margin: float = 0.0,
    min_event_action_score: float = -0.20,
):
    router = RerankedEventActionRouterV96(
        retrieval_threshold=retrieval_threshold,
        rerank_lambda=rerank_lambda,
        min_reranked_score=min_reranked_score,
        min_reranked_margin=min_reranked_margin,
        min_event_action_score=min_event_action_score,
    )
    for concept_id, examples in TRAIN.items():
        router.observe_concept(concept_id, examples)
    for concept_id, sentence in _protocol.iter_concept_counterexamples():
        router.observe_counterexample(concept_id, sentence)
    for sentence in _protocol.iter_global_actions():
        router.observe_action(sentence)
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
                print({"kind": kind, "expected": expected, "predicted": predicted,
                       "source": result.source, "positive_score": result.positive_score,
                       "negative_score": result.negative_score, "reranked_score": result.reranked_score,
                       "reranked_margin": result.reranked_margin, "event_action_score": result.event_action_score,
                       "sentence": sentence})
    metrics = {
        "protocol_id": PROTOCOL_ID, "n": len(ADVERSARIAL), "known_queries": known,
        "open_set_queries": negatives, "accuracy": correct / len(ADVERSARIAL),
        "known_recall": known_ok / known, "open_set_false_positive_rate": fp / negatives,
        "wrong_known_class_rate": wrong / known, "known_abstention_rate": abstained / known,
        "errors_by_kind": dict(errors),
    }
    if verbose:
        print("reranked_event_action_adversarial_v96")
        print(_protocol.protocol_summary())
        print(metrics)
        print("confusion_matrix")
        for expected in sorted(matrix):
            print(expected, dict(matrix[expected]))
    return metrics


def main() -> None:
    evaluate(build(), verbose=True)


if __name__ == "__main__":
    main()
