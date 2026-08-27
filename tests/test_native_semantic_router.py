from __future__ import annotations

import pytest

from memoria_resolutiva.semantic_router_v96 import AdaptiveSemanticRouterV96, SemanticRouterV96
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


def build(use_native: bool, *, native_authoritative: bool | None = False) -> SemanticRouterV96:
    router = SemanticRouterV96(threshold=0.0,min_margin=0.0,use_native=use_native,native_authoritative=native_authoritative)
    router.observe(CORPUS)
    for concept_id, anchors in CONCEPTS.items():router.register_concept(concept_id, anchors)
    return router

@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_native_router_matches_python_top_two_decision():
    py=build(False);native=build(True)
    for query in ["gato","cachorro","carro","moto","maçã","banana","servidor","roteador","animal","rede"]:
        expected=py.resolve_token(query);actual=native.resolve_token(query)
        assert actual.concept_id==expected.concept_id;assert actual.source==expected.source
        assert actual.score==pytest.approx(expected.score,abs=1e-12);assert actual.margin==pytest.approx(expected.margin,abs=1e-12)

@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_native_authoritative_router_matches_python_reference():
    py=build(False);authoritative=build(True,native_authoritative=True)
    assert authoritative.native_authoritative;assert not authoritative.memory.python_mirror_enabled;assert not authoritative.memory.associator.profiles
    for query in ["gato","cachorro","carro","moto","maçã","banana","servidor","roteador","animal","rede"]:
        expected=py.resolve_token(query);actual=authoritative.resolve_token(query)
        assert actual.concept_id==expected.concept_id;assert actual.source==expected.source
        assert actual.score==pytest.approx(expected.score,abs=1e-12);assert actual.margin==pytest.approx(expected.margin,abs=1e-12)

@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_native_full_scan_defaults_to_authoritative_mode():
    router=SemanticRouterV96(use_native=True);assert router.native_authoritative;assert router.memory.native_enabled;assert not router.memory.python_mirror_enabled

@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_native_mirror_can_be_forced_for_debug_or_profile_consumers():
    router=SemanticRouterV96(use_native=True,native_authoritative=False);router.observe(["q a b"])
    assert not router.native_authoritative;assert router.memory.python_mirror_enabled;assert router.memory.associator.profiles

@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_indexed_native_mode_keeps_python_mirror_by_default():
    router=SemanticRouterV96(use_native=True,indexed=True);router.observe(["q a b"])
    assert not router.native_authoritative;assert router.memory.python_mirror_enabled;assert router.memory.associator.profiles

@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_native_authoritative_rejects_python_index_dependency():
    with pytest.raises(ValueError,match="indexed=False"):SemanticRouterV96(use_native=True,native_authoritative=True,indexed=True)

@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_native_router_preserves_lexicographic_tie_break():
    py=SemanticRouterV96(threshold=0.0,min_margin=0.0,use_native=False);native=SemanticRouterV96(threshold=0.0,min_margin=0.0,use_native=True,native_authoritative=False)
    corpus=["q a b","q c d"]*20
    for router in (py,native):router.observe(corpus);router.register_concept("zeta",["a"]);router.register_concept("alpha",["c"])
    expected=py.resolve_token("q");actual=native.resolve_token("q")
    assert actual.concept_id==expected.concept_id;assert actual.score==pytest.approx(expected.score,abs=1e-12);assert actual.margin==pytest.approx(expected.margin,abs=1e-12)

@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_adaptive_router_switches_only_after_threshold_and_matches_full_scan():
    full=SemanticRouterV96(threshold=0.0,min_margin=0.0,use_native=True)
    adaptive=AdaptiveSemanticRouterV96(threshold=0.0,min_margin=0.0,use_native=True,adaptive_threshold=16,candidate_limit=8)
    sentences=[]
    for i in range(32):sentences.extend([f"conceito{i} grupo{i} sinal{i} comum",f"termo{i} grupo{i} sinal{i} comum"])
    for router in (full,adaptive):router.observe(sentences)
    for i in range(15):
        full.register_concept(f"c{i}",[f"conceito{i}"]);adaptive.register_concept(f"c{i}",[f"conceito{i}"])
    assert adaptive.resolve_token("termo7").concept_id==full.resolve_token("termo7").concept_id;assert adaptive.last_route_mode=="full"
    full.register_concept("c15",["conceito15"]);adaptive.register_concept("c15",["conceito15"])
    for i in range(16,32):full.register_concept(f"c{i}",[f"conceito{i}"]);adaptive.register_concept(f"c{i}",[f"conceito{i}"])
    for q in ["termo1","termo7","termo15","termo31"]:
        expected=full.resolve_token(q);actual=adaptive.resolve_token(q)
        assert adaptive.last_route_mode=="discriminative";assert adaptive.last_candidate_count<=8
        assert actual.concept_id==expected.concept_id;assert actual.score==pytest.approx(expected.score,abs=1e-12);assert actual.margin==pytest.approx(expected.margin,abs=1e-12)

@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_adaptive_router_falls_back_to_full_when_pruning_has_no_candidates():
    router=AdaptiveSemanticRouterV96(threshold=0.0,min_margin=0.0,use_native=True,adaptive_threshold=2,candidate_limit=8)
    router.observe(["a x y","b m n"]*10);router.register_concept("ca",["a"]);router.register_concept("cb",["b"])
    result=router.resolve_token("unknown")
    assert router.last_route_mode=="full";assert result.concept_id is not None
