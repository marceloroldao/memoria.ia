import pytest

from memoria_resolutiva.authority_independence_v117 import AuthorityIndependenceMemoryV117


def _observe_pair(mem, *, authority_a=None, authority_b=None):
    mem.observe("A fonte Delta alimenta o controlador.", provenance="p1", origin="o1", confidence=0.9)
    mem.observe("A fonte Delta alimenta o controlador.", provenance="p2", origin="o2", confidence=0.8)
    if authority_a:
        mem.register_origin_authority("o1", authority_a)
    if authority_b:
        mem.register_origin_authority("o2", authority_b)


def test_two_origins_same_authority_count_as_one_authority():
    mem = AuthorityIndependenceMemoryV117()
    _observe_pair(mem, authority_a="controller-X", authority_b="controller-X")
    assert mem.infer_path("Delta", "controlador", min_independent_origins=2).inferred
    assert not mem.infer_path(
        "Delta", "controlador", min_independent_origins=2, min_independent_authorities=2
    ).inferred


def test_two_origins_distinct_authorities_pass_authority_gate():
    mem = AuthorityIndependenceMemoryV117()
    _observe_pair(mem, authority_a="controller-X", authority_b="controller-Y")
    result = mem.infer_path(
        "Delta", "controlador", min_independent_origins=2, min_independent_authorities=2
    )
    assert result.inferred
    assert result.paths[0].independent_authority_floor == 2


def test_unmapped_origins_preserve_previous_semantics():
    mem = AuthorityIndependenceMemoryV117()
    _observe_pair(mem)
    result = mem.infer_path(
        "Delta", "controlador", min_independent_origins=2, min_independent_authorities=2
    )
    assert result.inferred


def test_authority_mapping_is_immutable():
    mem = AuthorityIndependenceMemoryV117()
    mem.register_origin_authority("o1", "a1")
    with pytest.raises(ValueError):
        mem.register_origin_authority("o1", "a2")


def test_authority_gate_does_not_replace_origin_gate():
    mem = AuthorityIndependenceMemoryV117()
    mem.observe("A fonte Delta alimenta o controlador.", provenance="p1", origin="o1", confidence=0.9)
    mem.register_origin_authority("o1", "a1")
    assert not mem.infer_path(
        "Delta", "controlador", min_independent_origins=2, min_independent_authorities=1
    ).inferred


def test_reliability_and_authority_gates_remain_separate():
    mem = AuthorityIndependenceMemoryV117()
    _observe_pair(mem, authority_a="a1", authority_b="a2")
    for i in range(4):
        mem.adjudicate_origin(
            "o1", resolution_id=f"r1-{i}", confirmed=True, adjudicator_origins=[f"judge1-{i}"]
        )
        mem.adjudicate_origin(
            "o2", resolution_id=f"r2-{i}", confirmed=True, adjudicator_origins=[f"judge2-{i}"]
        )
    result = mem.infer_path(
        "Delta",
        "controlador",
        min_independent_origins=2,
        min_independent_authorities=2,
        min_origin_reliability=0.7,
    )
    assert result.inferred


def test_multihop_path_authority_floor_is_weakest_edge():
    mem = AuthorityIndependenceMemoryV117()
    mem.observe("A fonte Delta alimenta o controlador.", provenance="a", origin="o1", confidence=0.9)
    mem.observe("A fonte Delta alimenta o controlador.", provenance="b", origin="o2", confidence=0.9)
    mem.observe("O controlador controlador pertence ao Orion.", provenance="c", origin="o3", confidence=0.9)
    mem.observe("O controlador controlador pertence ao Orion.", provenance="d", origin="o4", confidence=0.9)
    mem.register_origin_authority("o1", "auth1")
    mem.register_origin_authority("o2", "auth2")
    mem.register_origin_authority("o3", "auth3")
    mem.register_origin_authority("o4", "auth3")
    result = mem.infer_path("Delta", "Orion")
    assert result.inferred
    assert result.paths[0].independent_authority_floor == 1
