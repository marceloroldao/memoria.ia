from __future__ import annotations

from collections import Counter, defaultdict

from experiments.natural_language_split_v96 import TRAIN, TEST
from memoria_resolutiva.trajectory_contrastive_v96 import TrajectoryContrastiveRouterV96


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


def build() -> TrajectoryContrastiveRouterV96:
    router = TrajectoryContrastiveRouterV96(
        threshold=0.14,
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


def main():
    router = build()
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    positive = positive_ok = false_positive = wrong_known = abstained = 0

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

        if predicted != expected:
            print({
                "expected": expected,
                "predicted": predicted,
                "source": result.source,
                "positive_score": result.positive_score,
                "negative_score": result.negative_score,
                "contrast_margin": result.contrast_margin,
                "sentence": sentence,
            })

    n = len(TEST)
    negatives = sum(1 for expected, _ in TEST if expected is None)
    print({
        "accuracy": sum(matrix[k][k] for k in matrix) / n,
        "known_recall": positive_ok / positive if positive else 0.0,
        "open_set_false_positive_rate": false_positive / negatives if negatives else 0.0,
        "wrong_known_class_rate": wrong_known / positive if positive else 0.0,
        "known_abstention_rate": abstained / positive if positive else 0.0,
    })
    print("confusion_matrix")
    for expected in sorted(matrix):
        print(expected, dict(matrix[expected]))


if __name__ == "__main__":
    main()
