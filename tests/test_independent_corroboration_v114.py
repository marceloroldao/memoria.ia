from memoria_resolutiva.independent_corroboration_v114 import IndependentCorroborationMemoryV114


def test_v114_repeated_same_origin_counts_once():
    mem = IndependentCorroborationMemoryV114()
    for i in range(5):
        mem.observe(
            "A fonte Delta alimenta o controlador.",
            provenance=f"copy-{i}",
            origin="same-report",
            confidence=0.9,
        )
    edges = mem.corroborated_edges()
    assert len(edges) == 1
    assert edges[0].independent_origins == ("same-report",)
    assert not mem.infer_path("Delta", "controlador", min_independent_origins=2).inferred


def test_v114_two_independent_origins_pass_gate():
    mem = IndependentCorroborationMemoryV114()
    mem.observe("A fonte Delta alimenta o controlador.", provenance="sensor-a", origin="origin-a", confidence=0.8)
    mem.observe("A fonte Delta alimenta o controlador.", provenance="sensor-b", origin="origin-b", confidence=0.9)
    result = mem.infer_path("Delta", "controlador", min_independent_origins=2)
    assert result.inferred
    assert result.paths[0].independent_origin_floor == 2
    assert set(result.paths[0].origins_by_edge[0]) == {"origin-a", "origin-b"}


def test_v114_confidence_gate_applies_before_origin_count():
    mem = IndependentCorroborationMemoryV114()
    mem.observe("A fonte Delta alimenta o controlador.", provenance="a", origin="a", confidence=0.95)
    mem.observe("A fonte Delta alimenta o controlador.", provenance="b", origin="b", confidence=0.40)
    assert not mem.infer_path(
        "Delta", "controlador", min_confidence=0.5, min_independent_origins=2
    ).inferred


def test_v114_does_not_fuse_confidence_across_origins():
    mem = IndependentCorroborationMemoryV114()
    mem.observe("A fonte Delta alimenta o controlador.", provenance="a", origin="a", confidence=0.70)
    mem.observe("A fonte Delta alimenta o controlador.", provenance="b", origin="b", confidence=0.80)
    edge = mem.corroborated_edges(min_independent_origins=2)[0]
    assert edge.best_confidence == 0.80
    assert dict(edge.origin_confidences) == {"a": 0.70, "b": 0.80}


def test_v114_single_value_corroboration_uses_active_epoch_only():
    mem = IndependentCorroborationMemoryV114()
    mem.observe("O controlador Delta pertence ao Orion.", origin="old-a", epoch=0)
    mem.observe("O controlador Delta pertence ao Orion.", origin="old-b", epoch=0)
    mem.observe("O controlador Delta pertence ao Vega.", origin="new-a", epoch=1)

    assert mem.infer_path("Delta", "Orion", epoch=0, min_independent_origins=2).inferred
    assert not mem.infer_path("Delta", "Orion", min_independent_origins=1).inferred
    assert mem.infer_path("Delta", "Vega", min_independent_origins=1).inferred
    assert not mem.infer_path("Delta", "Vega", min_independent_origins=2).inferred


def test_v114_namespace_isolation_is_preserved():
    mem = IndependentCorroborationMemoryV114()
    mem.observe("A fonte Delta alimenta o controlador.", namespace="alpha", origin="a")
    mem.observe("A fonte Delta alimenta o controlador.", namespace="beta", origin="b")
    assert mem.infer_path("Delta", "controlador", namespace="alpha").inferred
    assert not mem.infer_path(
        "Delta", "controlador", namespace="alpha", min_independent_origins=2
    ).inferred


def test_v114_path_origin_floor_is_weakest_edge_count():
    mem = IndependentCorroborationMemoryV114()
    for origin in ("a", "b"):
        mem.observe("A fonte Delta alimenta o controlador.", origin=origin, confidence=0.9)
    mem.observe("O controlador controlador pertence ao Orion.", origin="a", confidence=0.85)
    result = mem.infer_path("Delta", "Orion")
    assert result.inferred
    assert result.paths[0].independent_origin_floor == 1
    assert result.paths[0].confidence == 0.85
