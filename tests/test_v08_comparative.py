from memoria_resolutiva.baselines import WindowCooccurrenceBaseline
from memoria_resolutiva.textual import TextContextMemory


def _corpus():
    return [
        "o carro atravessou a estrada durante a chuva",
        "o automovel atravessou a estrada durante a chuva",
        "pela manhã o carro ficou estacionado perto da oficina",
        "pela manhã o automovel ficou estacionado perto da oficina",
        "o sistema precisa guardar os dados antes da reinicialização",
        "o sistema precisa armazenar os dados antes da reinicialização",
        "vamos guardar os registros em local seguro",
        "vamos armazenar os registros em local seguro",
        "a fibra apresentou perda elevada durante a medição",
        "o enlace apresentou perda elevada durante a medição",
        "técnicos analisaram a fibra depois da falha óptica",
        "técnicos analisaram o enlace depois da falha óptica",
        "a estrela apareceu brilhante no céu noturno",
        "o astro apareceu brilhante no céu noturno",
        "cientistas observaram a estrela com o telescópio",
        "cientistas observaram o astro com o telescópio",
    ] + [
        "o cabo apresentou perda elevada durante a medição",
        "o planeta apareceu brilhante no céu noturno",
        "o veículo atravessou a estrada durante a chuva",
        "o programa deve salvar os dados antes da reinicialização",
    ] * 3


def _top1(model_similarity, query, candidates):
    return max(
        ((candidate, model_similarity(query, candidate)) for candidate in candidates if candidate != query),
        key=lambda item: item[1],
    )[0]


def test_signed_context_recovers_hidden_pairs_under_distractors():
    sentences = _corpus()
    model = TextContextMemory(radius=3)
    model.observe_many(sentences)
    candidates = ["carro", "automovel", "guardar", "armazenar", "fibra", "enlace", "estrela", "astro", "cabo", "planeta", "veículo", "salvar"]
    expected = {
        "carro": "automovel", "automovel": "carro",
        "guardar": "armazenar", "armazenar": "guardar",
        "fibra": "enlace", "enlace": "fibra",
        "estrela": "astro", "astro": "estrela",
    }
    assert all(_top1(model.associator.similarity, q, candidates) == target for q, target in expected.items())


def test_comparison_baseline_is_available_and_non_neural():
    baseline = WindowCooccurrenceBaseline(radius=3)
    baseline.observe_many(_corpus())
    assert baseline.similarity("carro", "automovel") > 0.0
