from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96


def build_router():
    r = SemanticRouterV96(threshold=0.55, min_margin=0.05)
    r.observe([
        "a tarifa mensal foi aplicada ao servico de fibra",
        "a cobranca mensal foi aplicada ao servico de fibra",
        "o encargo mensal foi aplicado ao servico de fibra",
        "a estrela brilhante apareceu no ceu noturno",
        "o astro brilhante apareceu no ceu noturno",
        "a estrela distante foi observada pelo telescopio",
        "o astro distante foi observado pelo telescopio",
    ])
    r.register_concept("fee", ["tarifa"])
    r.register_concept("star", ["estrela"])
    return r


def test_contextual_synonym_routes_without_manual_synonym_map():
    r = build_router()
    result = r.resolve_token("cobranca")
    assert result.concept_id == "fee"
    assert result.source == "memory"


def test_unrelated_domain_is_not_misrouted():
    r = build_router()
    result = r.resolve_token("telescopio")
    assert result.concept_id is None


def test_ambiguous_or_unknown_query_uses_fallback():
    r = build_router()
    calls = []

    def fallback(q):
        calls.append(q)
        return "external"

    result = r.resolve_or_fallback("palavra-inexistente", fallback)
    assert result.source == "fallback"
    assert result.concept_id == "external"
    assert calls == ["palavra-inexistente"]


def test_deflection_metric_counts_avoided_fallback_calls():
    r = build_router()
    calls = []

    def fallback(q):
        calls.append(q)
        return "external"

    for q in ["cobranca", "encargo", "astro", "desconhecido"]:
        r.resolve_or_fallback(q, fallback)

    m = r.metrics()
    assert m.total_queries == 4
    assert m.memory_resolved == 3
    assert m.fallback_calls == 1
    assert m.deflection_rate == 0.75
