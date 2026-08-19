from __future__ import annotations

import importlib.util
from collections import Counter, defaultdict
from pathlib import Path

from memoria_resolutiva.trajectory_contrastive_v96 import TrajectoryContrastiveRouterV96

_HERE = Path(__file__).resolve().parent
_SPLIT_PATH = _HERE / "natural_language_split_v96.py"
_spec = importlib.util.spec_from_file_location("natural_language_split_v96", _SPLIT_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load benchmark dataset: {_SPLIT_PATH}")
_split = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_split)
TRAIN = _split.TRAIN
TEST = _split.TEST

COUNTEREXAMPLES = {
    "payment_delay": [
        "foi emitido um comprovante de pagamento ja realizado",
        "o cliente apresentou recibo de uma fatura que ja foi quitada",
    ],
    "optical_loss": [
        "o tecnico substituiu a fonte de alimentacao da onu",
        "a onu recebeu uma nova fonte eletrica durante manutencao",
    ],
    "account_block": [
        "o usuario quer atualizar telefone e email do cadastro",
        "o cliente solicitou apenas alteracao cadastral sem bloqueio de acesso",
    ],
}


def build(threshold: float) -> TrajectoryContrastiveRouterV96:
    router = TrajectoryContrastiveRouterV96(
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
    return router


def evaluate(threshold: float):
    router = build(threshold)
    positive = positive_ok = false_positive = wrong_known = abstained = 0
    matrix: dict[str, Counter[str]] = defaultdict(Counter)

    for expected, sentence in TEST:
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

    negatives = sum(1 for expected, _ in TEST if expected is None)
    n = len(TEST)
    return {
        "threshold": threshold,
        "accuracy": sum(matrix[k][k] for k in matrix) / n,
        "known_recall": positive_ok / positive if positive else 0.0,
        "open_set_false_positive_rate": false_positive / negatives if negatives else 0.0,
        "wrong_known_class_rate": wrong_known / positive if positive else 0.0,
        "known_abstention_rate": abstained / positive if positive else 0.0,
    }


def main():
    for threshold in (0.10, 0.11, 0.12, 0.125, 0.13, 0.135, 0.14):
        print(evaluate(threshold))


if __name__ == "__main__":
    main()
