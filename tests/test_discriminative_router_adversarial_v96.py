from memoria_resolutiva.discriminative_router_v96 import DiscriminativeSemanticRouterV96
from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96


def build_pair(limit=8):
    full = SemanticRouterV96(threshold=0.45, min_margin=0.05, indexed=False)
    disc = DiscriminativeSemanticRouterV96(
        threshold=0.45,
        min_margin=0.05,
        candidate_limit=limit,
    )

    sentences = []
    # Families deliberately share most context. Only one or two features separate neighbors.
    for family in range(20):
        for variant in range(10):
            i = family * 10 + variant
            anchor = f"conceito{i}"
            synonym = f"termo{i}"
            shared = f"familia{family} canal{family % 5}"
            rare = f"assinatura{i}"
            sentences.extend([
                f"o {anchor} {shared} {rare} opera no sistema comum",
                f"o {synonym} {shared} {rare} opera no sistema comum",
            ])

    full.observe(sentences)
    disc.observe(sentences)
    for i in range(200):
        cid = f"c{i}"
        full.register_concept(cid, [f"conceito{i}"])
        disc.register_concept(cid, [f"conceito{i}"])
    return full, disc


def test_limit8_matches_full_scan_on_near_neighbors():
    full, disc = build_pair(limit=8)
    for i in range(200):
        q = f"termo{i}"
        assert full.resolve_token(q).concept_id == f"c{i}"
        assert disc.resolve_token(q).concept_id == f"c{i}"


def test_shared_family_context_without_unique_signal_abstains():
    full, disc = build_pair(limit=8)
    # This token is observed with family context but has no unique concept signature.
    disc.observe(["o consultaambigua familia3 canal3 opera no sistema comum"])
    full.observe(["o consultaambigua familia3 canal3 opera no sistema comum"])
    assert full.resolve_token("consultaambigua").concept_id is None
    assert disc.resolve_token("consultaambigua").concept_id is None


def test_unknown_stays_unresolved_under_candidate_pressure():
    _, disc = build_pair(limit=8)
    assert disc.resolve_token("fora_do_vocabulario").concept_id is None
