from __future__ import annotations

import itertools

import pytest

from memoria_resolutiva.textual import TextContextMemory, native_context_available

pytestmark = pytest.mark.skipif(not native_context_available(), reason="native core extension not built")


CORPUS = [
    "a lua orbita a terra em trajetória estável",
    "a terra orbita o sol em trajetória maior",
    "memória contextual relaciona estado trajetória e tempo",
    "estado local recupera contexto sem rede neural",
    "trajetória resolutiva liga memória estado e contexto",
    "lua terra sol formam relações em escalas diferentes",
    "contexto local seleciona memória relevante para consulta",
]


def _build(use_native: bool, *, mirror_python: bool = True) -> TextContextMemory:
    memory = TextContextMemory(radius=3, use_native=use_native, mirror_python=mirror_python)
    memory.observe_many(CORPUS)
    return memory


def test_native_similarity_matches_python_reference():
    pure = _build(False)
    native = _build(True)
    tokens = sorted(pure.associator.profiles)
    for a, b in itertools.product(tokens, repeat=2):
        assert native.similarity(a, b) == pytest.approx(pure.similarity(a, b), abs=1e-12, rel=1e-12)


def test_native_unordered_similarity_matches_python_reference():
    pure = _build(False)
    native = _build(True)
    tokens = sorted(pure.associator.profiles)
    for a, b in itertools.product(tokens, repeat=2):
        assert native.unordered_similarity(a, b) == pytest.approx(
            pure.unordered_similarity(a, b), abs=1e-12, rel=1e-12
        )


def test_native_path_preserves_python_profiles_for_indexing():
    pure = _build(False)
    native = _build(True)
    assert native.associator.profiles == pure.associator.profiles
    assert native.associator.feature_df == pure.associator.feature_df
    assert native.associator.observations == pure.associator.observations


def test_native_authoritative_skips_python_mirror_and_preserves_scores():
    pure = _build(False)
    authoritative = _build(True, mirror_python=False)
    assert authoritative.native_enabled
    assert not authoritative.python_mirror_enabled
    assert not authoritative.associator.profiles
    assert not authoritative.associator.feature_df
    assert not authoritative.associator.observations
    tokens = sorted(pure.associator.profiles)
    for a, b in itertools.product(tokens, repeat=2):
        assert authoritative.similarity(a, b) == pytest.approx(pure.similarity(a, b), abs=1e-12, rel=1e-12)
        assert authoritative.unordered_similarity(a, b) == pytest.approx(
            pure.unordered_similarity(a, b), abs=1e-12, rel=1e-12
        )


def test_native_authoritative_nearest_matches_reference():
    pure = _build(False)
    authoritative = _build(True, mirror_python=False)
    for token in ["lua", "terra", "trajetória", "contexto", "estado"]:
        expected = pure.nearest(token, top_k=5)
        actual = authoritative.nearest(token, top_k=5)
        assert [name for name, _ in actual] == [name for name, _ in expected]
        for (_, actual_score), (_, expected_score) in zip(actual, expected):
            assert actual_score == pytest.approx(expected_score, abs=1e-12, rel=1e-12)
