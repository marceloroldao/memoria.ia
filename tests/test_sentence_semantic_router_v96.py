from memoria_resolutiva.sentence_semantic_router_v96 import SentenceSemanticRouterV96


def build():
    r = SentenceSemanticRouterV96(threshold=0.14, min_margin=0.02)
    r.observe_concept("billing", [
        "a tarifa mensal foi aplicada ao servico",
        "o encargo adicional apareceu na cobranca",
        "a taxa consta na fatura do cliente",
    ])
    r.observe_concept("outage", [
        "a conexao caiu depois de uma falha na rede",
        "o cliente ficou sem internet por indisponibilidade",
        "houve interrupcao total do servico",
    ])
    r.observe_concept("latency", [
        "a rede respondeu lentamente com atraso elevado",
        "a latencia subiu durante congestionamento",
        "o ping aumentou apesar do link permanecer ativo",
    ])
    return r


def test_noisy_billing_sentence_routes_to_billing():
    r = build()
    out = r.resolve("o cliente reclamou que apareceu uma cobranca extra na conta deste mes")
    assert out.concept_id == "billing"


def test_long_latency_sentence_uses_full_context():
    r = build()
    out = r.resolve("o link nao caiu mas tudo demora muito para responder e o ping aumentou bastante")
    assert out.concept_id == "latency"


def test_unrelated_sentence_abstains():
    r = build()
    out = r.resolve("o cliente marcou uma visita tecnica para sexta feira")
    assert out.concept_id is None
