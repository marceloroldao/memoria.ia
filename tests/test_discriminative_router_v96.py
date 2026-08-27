import pytest

from memoria_resolutiva.discriminative_router_v96 import DiscriminativeSemanticRouterV96
from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96
from memoria_resolutiva.textual import native_context_available


def build_pair(n=64, *, disc_native=None):
    full = SemanticRouterV96(threshold=0.45, min_margin=0.05, indexed=False, use_native=False)
    disc = DiscriminativeSemanticRouterV96(
        threshold=0.45,
        min_margin=0.05,
        candidate_limit=16,
        use_native=disc_native,
    )
    sentences = []
    for i in range(n):
        anchor = f"conceito{i}"
        synonym = f"termo{i}"
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
    full, disc = build_pair(disc_native=False)
    for i in range(64):
        q = f"termo{i}"
        a = full.resolve_token(q)
        b = disc.resolve_token(q)
        assert a.concept_id == f"c{i}"
        assert b.concept_id == a.concept_id


def test_discriminative_router_reduces_candidate_set():
    _, disc = build_pair(128, disc_native=False)
    r = disc.resolve_token("termo77")
    assert r.concept_id == "c77"
    stats = disc.candidate_stats()
    assert stats.candidate_concepts <= 16
    assert stats.retained_fraction <= 0.125


def test_unknown_remains_unresolved():
    _, disc = build_pair(disc_native=False)
    assert disc.resolve_token("nao_observado").concept_id is None


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_native_discriminative_candidates_match_python_reference():
    _, py = build_pair(128, disc_native=False)
    _, native = build_pair(128, disc_native=True)
    assert native.native_authoritative
    assert not native.memory.python_mirror_enabled
    assert not native.memory.associator.profiles
    for i in range(128):
        q = f"termo{i}"
        expected_candidates = py._discriminative_candidates(q)
        actual_candidates = native._discriminative_candidates(q)
        assert actual_candidates == expected_candidates


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_native_discriminative_resolution_matches_python_reference():
    _, py = build_pair(128, disc_native=False)
    _, native = build_pair(128, disc_native=True)
    for i in range(128):
        q = f"termo{i}"
        expected = py.resolve_token(q)
        actual = native.resolve_token(q)
        assert actual.concept_id == expected.concept_id
        assert actual.source == expected.source
        assert actual.score == pytest.approx(expected.score, abs=1e-12)
        assert actual.margin == pytest.approx(expected.margin, abs=1e-12)
        assert native.candidate_stats() == py.candidate_stats()


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_native_discriminative_default_is_authoritative():
    router = DiscriminativeSemanticRouterV96(use_native=True)
    assert router.native_authoritative
    assert router.memory.native_enabled
    assert not router.memory.python_mirror_enabled
