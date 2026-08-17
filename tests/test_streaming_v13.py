from memoria_resolutiva.contextual import ContextAssociator
from memoria_resolutiva.streaming import StreamingLearningEvaluator


def test_feature_document_frequency_is_maintained_incrementally():
    associator = ContextAssociator(radius=1)
    associator.observe(["a", "x", "b"])
    first = dict(associator.feature_df)
    associator.observe(["a", "x", "b"])
    # Re-observing the same node-feature relation increases counts in the node
    # profile, but document frequency must not increase twice for the same node.
    assert dict(associator.feature_df) == first
    assert associator.footprint()["nodes"] == 3


def test_streaming_learning_is_immediate_and_retains_prior_pair():
    evaluator = StreamingLearningEvaluator(radius=2)
    first = [
        "carro estrada cidade",
        "automovel estrada cidade",
        "motorista carro viagem",
        "motorista automovel viagem",
    ] * 12
    second = [
        "fibra sinal rede",
        "enlace sinal rede",
        "equipamento fibra transmissao",
        "equipamento enlace transmissao",
    ] * 12

    step1 = evaluator.observe_batch(first, ("carro", "automovel"))
    step2 = evaluator.observe_batch(second, ("fibra", "enlace"))

    assert step1.immediate_top1 == 1.0
    assert step2.immediate_top1 == 1.0
    assert step2.retention_top1 == 1.0
    assert step2.sentences_seen == len(first) + len(second)
    assert step2.features >= step1.features
