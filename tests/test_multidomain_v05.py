from experiments.multidomain_v05 import PAIRS, build_corpus
from memoria_resolutiva.evaluation import evaluate_hidden_pairs


def test_hidden_pairs_rank_top1_in_controlled_multidomain_corpus():
    model = build_corpus(exposures=20, noise_trajectories=500, seed=42)
    metrics = evaluate_hidden_pairs(model, PAIRS, top_k=3)
    assert metrics.queries == 8
    assert metrics.top1_correct == 8
    assert metrics.top1_accuracy == 1.0
    assert metrics.topk_recall == 1.0


def test_noise_does_not_make_unrelated_pair_closer_than_hidden_pair():
    model = build_corpus(exposures=20, noise_trajectories=500, seed=42)
    assert model.similarity("carro", "automovel") > model.similarity("carro", "estrela")
    assert model.similarity("fibra", "enlace") > model.similarity("fibra", "astro")
