from memoria_resolutiva.online_learning import OnlineLearningEvaluator


def test_online_learning_is_immediate_and_retains_old_pair():
    evaluator = OnlineLearningEvaluator(radius=2)

    first = [
        "carro percorre estrada",
        "automovel percorre estrada",
        "motorista usa carro",
        "motorista usa automovel",
    ] * 10
    second = [
        "fibra transporta sinal",
        "enlace transporta sinal",
        "rede usa fibra",
        "rede usa enlace",
    ] * 10

    s1 = evaluator.observe_batch(first, ("carro", "automovel"))
    assert s1.immediate_top1 == 1.0
    assert s1.retention_top1 == 1.0

    s2 = evaluator.observe_batch(second, ("fibra", "enlace"))
    assert s2.immediate_top1 == 1.0
    assert s2.retention_top1 == 1.0
    assert s2.observations == len(first) + len(second)
