from memoria_resolutiva.discriminative_router_v96 import DiscriminativeSemanticRouterV96
from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96


def build_pair(n=64):
    full = SemanticRouterV96(threshold=0.45, min_margin=0.05, indexed=False)
    disc = DiscriminativeSemanticRouterV96(
        threshold=0.45,
        min_margin=0.05,
        candidate_limit=16,
    )
    sentences = []
    for i in range(n):
        anchor = f"conceito{i}"
        synonym = f"termo{i}"
        # Rare discriminators deliberately sit inside radius=3.
        sentences.extend([
            f"o {anchor} grupo{i} sinal{i} aparece no sistema comum",
            f"o {synonym} grupo{i} sinal{i} aparece no sistema comum",
        ])
    full.observe(sentences)
    disc.observe(sentences)
    for i in range(n):
        full.register_concept(f"c{i}", [f"conceito{i}"])
        disc.register_concept(f"c{i}", [f"conceito{i}"])
    return full, disc


def test_discriminative_router_matches_full_scan_on_controlled_concepts():
    full, disc = build_pair()
    for i in range(64):
        q = f"termo{i}"
        a = full.resolve_token(q)
        b = disc.resolve_token(q)
        assert a.concept_id == f"c{i}"
        assert b.concept_id == a.concept_id


def test_discriminative_router_reduces_candidate_set():
    _, disc = build_pair(128)
    r = disc.resolve_token("termo77")
    assert r.concept_id == "c77"
    stats = disc.candidate_stats()
    assert stats.candidate_concepts <= 16
    assert stats.retained_fraction <= 0.125


def test_unknown_remains_unresolved():
    _, disc = build_pair()
    assert disc.resolve_token("nao_observado").concept_id is None
