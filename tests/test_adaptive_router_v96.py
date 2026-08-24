from memoria_resolutiva.adaptive_router_v96 import AdaptiveDiscriminativeSemanticRouterV96


def build_router():
    r = AdaptiveDiscriminativeSemanticRouterV96(
        threshold=0.45,
        min_margin=0.05,
        candidate_ladder=(8, 16, 32, 64),
    )
    sentences = []
    for i in range(80):
        family = i // 10
        sentences.extend([
            f"conceito{i} familia{family} assinatura{i} evento{i}",
            f"termo{i} familia{family} assinatura{i} evento{i}",
        ])
    r.observe(sentences)
    for i in range(80):
        r.register_concept(f"c{i}", [f"conceito{i}"])
    return r


def test_easy_query_resolves_without_expansion():
    r = build_router()
    got = r.resolve_token("termo17")
    assert got.concept_id == "c17"
    stats = r.adaptive_stats()
    assert stats.attempted_limits[0] == 8
    assert stats.final_limit == 8
    assert not stats.expanded


def test_unknown_query_stays_unresolved():
    r = build_router()
    got = r.resolve_token("nao_observado")
    assert got.concept_id is None


def test_candidate_ladder_is_validated():
    try:
        AdaptiveDiscriminativeSemanticRouterV96(candidate_ladder=(1, 8))
    except ValueError:
        pass
    else:
        raise AssertionError("candidate ladder below 2 must be rejected")
