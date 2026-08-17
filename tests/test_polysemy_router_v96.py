from memoria_resolutiva.polysemy_router_v96 import PolysemyRouterV96


def build_router():
    r = PolysemyRouterV96(threshold=0.25, min_margin=0.08)
    r.observe_sense("banco", "financial_bank", [
        "o banco aprovou o credito do cliente",
        "o banco recebeu o deposito na conta",
        "o banco cobrou juros do financiamento",
    ])
    r.observe_sense("banco", "seat_bench", [
        "o banco de madeira fica no parque",
        "sentamos no banco perto da arvore",
        "o banco da praca estava molhado pela chuva",
    ])
    return r


def test_financial_sense_routes_from_context():
    r = build_router()
    x = r.resolve("banco", "o banco liberou credito para a conta do cliente")
    assert x.concept_id == "financial_bank"
    assert x.source == "memory"


def test_bench_sense_routes_from_context():
    r = build_router()
    x = r.resolve("banco", "sentamos no banco de madeira perto do parque")
    assert x.concept_id == "seat_bench"
    assert x.source == "memory"


def test_ambiguous_context_abstains():
    r = build_router()
    x = r.resolve("banco", "eu vi o banco ontem")
    assert x.concept_id is None
    assert x.source == "unresolved"


def test_fallback_only_for_ambiguous_case():
    r = build_router()
    calls = []

    def fallback(surface, sentence):
        calls.append((surface, sentence))
        return "external"

    queries = [
        ("banco", "o banco aprovou credito para o cliente"),
        ("banco", "o banco de madeira estava no parque"),
        ("banco", "eu encontrei o banco ontem"),
    ]
    results = [r.resolve_or_fallback(*q, fallback) for q in queries]
    assert [x.source for x in results] == ["memory", "memory", "fallback"]
    assert len(calls) == 1
    assert r.metrics()["deflection_rate"] == 2 / 3
