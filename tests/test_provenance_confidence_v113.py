from memoria_resolutiva.provenance_confidence_v113 import ProvenanceConfidenceMemoryV113


def test_v113_path_confidence_is_weakest_edge():
    mem = ProvenanceConfidenceMemoryV113()
    mem.observe("A fonte Delta alimenta o controlador.", provenance="sensor:a", confidence=0.95)
    mem.observe("O controlador controlador pertence ao Orion.", provenance="registry:b", confidence=0.60)
    result = mem.infer_path("Delta", "Orion")
    assert result.inferred
    path = result.paths[0]
    assert path.confidence == 0.60
    assert path.edge_confidences == (0.95, 0.60)
    assert path.provenances == ("sensor:a", "registry:b")


def test_v113_min_confidence_filters_weak_edge_and_abstains():
    mem = ProvenanceConfidenceMemoryV113()
    mem.observe("A fonte Delta alimenta o controlador.", confidence=0.95)
    mem.observe("O controlador controlador pertence ao Orion.", confidence=0.40)
    assert mem.infer_path("Delta", "Orion", min_confidence=0.50).inferred is False


def test_v113_min_confidence_keeps_supported_path():
    mem = ProvenanceConfidenceMemoryV113()
    mem.observe("A fonte Delta alimenta o controlador.", confidence=0.95)
    mem.observe("O controlador controlador pertence ao Orion.", confidence=0.80)
    result = mem.infer_path("Delta", "Orion", min_confidence=0.75)
    assert result.inferred
    assert result.paths[0].confidence == 0.80


def test_v113_rejects_invalid_confidence_values():
    mem = ProvenanceConfidenceMemoryV113()
    for value in (-0.01, 1.01):
        try:
            mem.observe("A fonte Delta alimenta o controlador.", confidence=value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid confidence must raise")


def test_v113_preserves_temporal_supersession():
    mem = ProvenanceConfidenceMemoryV113()
    mem.observe("O controlador controlador pertence ao Orion.", epoch=0, confidence=0.90)
    mem.observe("O controlador controlador pertence ao Vega.", epoch=1, confidence=0.90)
    assert mem.infer_path("controlador", "Orion", epoch=0).inferred
    assert not mem.infer_path("controlador", "Orion").inferred
    assert mem.infer_path("controlador", "Vega").inferred


def test_v113_preserves_namespace_isolation():
    mem = ProvenanceConfidenceMemoryV113()
    mem.observe("A fonte Delta alimenta o controlador.", namespace="alpha", confidence=1.0)
    mem.observe("O controlador controlador pertence ao Orion.", namespace="beta", confidence=1.0)
    assert not mem.infer_path("Delta", "Orion", namespace="alpha").inferred
    assert not mem.infer_path("Delta", "Orion", namespace="beta").inferred


def test_v113_ranks_stronger_path_first():
    mem = ProvenanceConfidenceMemoryV113()
    mem.observe("A fonte Delta alimenta o controlador.", confidence=0.95)
    mem.observe("O controlador controlador pertence ao Orion.", confidence=0.70)
    mem.observe("A fonte Delta alimenta o módulo.", confidence=0.90)
    mem.observe("O módulo módulo pertence ao Orion.", confidence=0.85)
    result = mem.infer_path("Delta", "Orion", max_paths=5)
    assert len(result.paths) == 2
    assert result.paths[0].confidence == 0.85
    assert result.paths[1].confidence == 0.70
