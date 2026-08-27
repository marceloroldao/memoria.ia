from __future__ import annotations

import pytest

from memoria_resolutiva.semantic_router_v96 import AdaptiveSemanticRouterV96, SemanticRouterV96
from memoria_resolutiva.textual import native_context_available

pytestmark = pytest.mark.skipif(not native_context_available(), reason="native core unavailable")


def _build_pair(n: int = 256):
    full = SemanticRouterV96(threshold=0.0, min_margin=0.0, use_native=True)
    adaptive = AdaptiveSemanticRouterV96(
        threshold=0.0,
        min_margin=0.0,
        use_native=True,
        adaptive_threshold=64,
        candidate_limit=32,
    )
    sentences: list[str] = []
    for i in range(n):
        family = i % 16
        band = (i // 16) % 4
        # Most context is deliberately shared. Two rare discriminators preserve
        # identity while repeated noise creates strong overlap between concepts.
        sentences.extend(
            [
                f"anchor{i} familia{family} banda{band} comum sistema dados rede ruido{i % 11}",
                f"query{i} familia{family} banda{band} comum sistema dados rede ruido{(i + 3) % 11}",
                f"anchor{i} query{i} assinatura{i} comum memoria contexto",
            ]
        )
    for router in (full, adaptive):
        router.observe(sentences)
        for i in range(n):
            router.register_concept(f"c{i}", [f"anchor{i}"])
    return full, adaptive


def _assert_same(full, adaptive, query: str) -> None:
    expected = full.resolve_token(query)
    actual = adaptive.resolve_token(query)
    assert actual.concept_id == expected.concept_id
    assert actual.source == expected.source
    assert actual.score == pytest.approx(expected.score, abs=1e-12, rel=1e-12)
    assert actual.margin == pytest.approx(expected.margin, abs=1e-12, rel=1e-12)


def test_adaptive_recall_matches_full_scan_under_shared_noisy_context():
    full, adaptive = _build_pair()
    for i in range(256):
        _assert_same(full, adaptive, f"query{i}")
        assert adaptive.last_route_mode == "discriminative"
        assert 1 <= adaptive.last_candidate_count <= 32


def test_adaptive_preserves_ambiguous_shared_queries_and_unknowns():
    full, adaptive = _build_pair()
    # Shared context is intentionally ambiguous; whatever the exact full-scan
    # decision/abstention is, adaptive routing must preserve it.
    for query in ["comum", "sistema", "dados", "rede", "memoria", "contexto", "nao_observado"]:
        _assert_same(full, adaptive, query)
