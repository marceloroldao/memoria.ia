from __future__ import annotations

import pytest

from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96
from memoria_resolutiva.textual import native_context_available


CORPUS = [
    "gato felino animal casa", "cachorro canino animal casa",
    "carro veiculo estrada motor", "moto veiculo estrada motor",
    "maçã fruta comida doce", "banana fruta comida doce",
    "servidor computador rede dados", "roteador rede pacote dados",
] * 20

CONCEPTS = {
    "animal": {"gato", "cachorro"},
    "veiculo": {"carro", "moto"},
    "alimento": {"maçã", "banana"},
    "tecnologia": {"servidor", "roteador"},
}


def build(use_native: bool) -> SemanticRouterV96:
    router = SemanticRouterV96(threshold=0.0, min_margin=0.0, use_native=use_native)
    router.observe(CORPUS)
    for concept_id, anchors in CONCEPTS.items():
        router.register_concept(concept_id, anchors)
    return router


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_native_router_matches_python_top_two_decision():
    py = build(False)
    native = build(True)
    for query in ["gato", "cachorro", "carro", "moto", "maçã", "banana", "servidor", "roteador", "animal", "rede"]:
        expected = py.resolve_token(query)
        actual = native.resolve_token(query)
        assert actual.concept_id == expected.concept_id
        assert actual.source == expected.source
        assert actual.score == pytest.approx(expected.score, abs=1e-12)
        assert actual.margin == pytest.approx(expected.margin, abs=1e-12)


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_native_router_preserves_lexicographic_tie_break():
    py = SemanticRouterV96(threshold=0.0, min_margin=0.0, use_native=False)
    native = SemanticRouterV96(threshold=0.0, min_margin=0.0, use_native=True)
    corpus = ["q a b", "q c d"] * 20
    for router in (py, native):
        router.observe(corpus)
        router.register_concept("zeta", ["a"])
        router.register_concept("alpha", ["c"])
    expected = py.resolve_token("q")
    actual = native.resolve_token("q")
    assert actual.concept_id == expected.concept_id
    assert actual.score == pytest.approx(expected.score, abs=1e-12)
    assert actual.margin == pytest.approx(expected.margin, abs=1e-12)
