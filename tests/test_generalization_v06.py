from experiments.generalization_v06 import build_model, PAIRS, DISTRACTORS
from memoria_resolutiva.generalization import evaluate_pairs


def test_hidden_pairs_survive_noise_and_distractors():
    model = build_model(noise=1000)
    metrics = evaluate_pairs(model, PAIRS, DISTRACTORS)
    assert metrics.top1_accuracy == 1.0
    assert metrics.mean_margin > 0.30


def test_adversarial_distractors_rank_below_expected_partner():
    model = build_model(noise=1000)
    for a, b in PAIRS:
        assert model.similarity(a, b) > max(
            model.similarity(a, d) for d in DISTRACTORS[a]
        )
        assert model.similarity(b, a) > max(
            model.similarity(b, d) for d in DISTRACTORS[b]
        )
