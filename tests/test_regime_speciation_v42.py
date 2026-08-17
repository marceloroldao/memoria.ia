from memoria_resolutiva.regime_speciation import RegimeLineageMemory


def test_close_variant_does_not_speciate():
    m = RegimeLineageMemory(variant_threshold=0.90, speciation_threshold=0.75, persistence=2)
    m.remember_root("A", [1.0, 0.8, 0.1, 0.0])
    state = m.observe_variant("A", [0.96, 0.76, 0.14, 0.04], "A1")
    assert state == "variant"
    assert "A1" not in m.nodes


def test_persistent_divergence_creates_child_regime():
    m = RegimeLineageMemory(variant_threshold=0.90, speciation_threshold=0.75, persistence=2)
    m.remember_root("A", [1.0, 0.8, 0.1, 0.0])
    s1 = m.observe_variant("A", [0.66, 0.46, 0.46, 0.30], "A3")
    s2 = m.observe_variant("A", [0.58, 0.38, 0.54, 0.38], "A4")
    assert s1 == "drifting"
    assert s2 == "speciated"
    assert "A4" in m.nodes
    assert m.nodes["A4"].parent == "A"


def test_lineage_is_preserved():
    m = RegimeLineageMemory(variant_threshold=0.90, speciation_threshold=0.75, persistence=1)
    m.remember_root("A", [1.0, 0.8, 0.1, 0.0])
    m.observe_variant("A", [0.50, 0.30, 0.60, 0.40], "A_child")
    assert m.lineage("A_child") == ["A", "A_child"]


def test_ambiguous_middle_similarity_does_not_force_speciation():
    m = RegimeLineageMemory(variant_threshold=0.90, speciation_threshold=0.70, persistence=2)
    m.remember_root("A", [1.0, 0.0, 0.0])
    # Similarity between thresholds should stay in drift region without immediate speciation.
    state = m.observe_variant("A", [0.75, 0.66, 0.0], "mid")
    assert state in {"drifting", "variant"}
    assert "mid" not in m.nodes
