from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96


def build(indexed: bool):
    r = SemanticRouterV96(threshold=0.45, min_margin=0.05, indexed=indexed)
    sentences = []
    for i in range(40):
        anchor = f"conceito{i}"
        alias = f"alias{i}"
        domain = f"dominio{i}"
        context = f"contexto{i}"
        sentences.extend([
            f"o {anchor} aparece no {domain} com {context}",
            f"o {alias} aparece no {domain} com {context}",
            f"o {anchor} permanece associado a {domain} e {context}",
            f"o {alias} permanece associado a {domain} e {context}",
        ])
        r.register_concept(f"c{i}", [anchor])
    r.observe(sentences)
    return r


def test_indexed_router_matches_full_scan_on_controlled_corpus():
    indexed = build(True)
    full = build(False)
    queries = [f"alias{i}" for i in range(40)] + ["desconhecido", "fora"]
    for query in queries:
        a = indexed.resolve_token(query)
        b = full.resolve_token(query)
        assert a.concept_id == b.concept_id
        assert abs(a.score - b.score) < 1e-12
        assert abs(a.margin - b.margin) < 1e-12


def test_index_rebuilds_after_new_observation_and_concept():
    r = build(True)
    assert r.resolve_token("alias0").concept_id == "c0"
    r.observe([
        "o especial aparece no dominioespecial com contextoespecial",
        "o alternativo aparece no dominioespecial com contextoespecial",
    ])
    r.register_concept("especial", ["especial"])
    assert r.resolve_token("alternativo").concept_id == "especial"
