from memoria_resolutiva.convergent_lineages import ConvergentLineageMemory


def build():
    m = ConvergentLineageMemory(convergence_threshold=0.90, ambiguity_band=0.03)
    m.remember("A", [1.0, 0.0, 0.1, 0.0])
    m.remember("A1", [0.8, 0.3, 0.2, 0.1], parent="A")
    m.remember("B", [0.0, 1.0, 0.0, 0.1])
    m.remember("B1", [0.75, 0.35, 0.2, 0.1], parent="B")
    return m


def test_convergence_creates_macro_without_erasing_lineages():
    m = build()
    d = m.compare("A1", "B1")
    assert d.kind == "convergent"
    assert d.macro_concept is not None
    assert m.ancestry("A1") == ["A1", "A"]
    assert m.ancestry("B1") == ["B1", "B"]
    assert set(m.members(d.macro_concept)) == {"A1", "B1"}


def test_distant_lineages_remain_independent():
    m = ConvergentLineageMemory(convergence_threshold=0.90)
    m.remember("X", [1.0, 0.0, 0.0])
    m.remember("Y", [0.0, 1.0, 0.0])
    d = m.compare("X", "Y")
    assert d.kind == "independent"
    assert d.macro_concept is None


def test_borderline_similarity_can_abstain():
    m = ConvergentLineageMemory(convergence_threshold=0.90, ambiguity_band=0.05)
    m.remember("X", [1.0, 0.0])
    m.remember("Y", [0.90, 0.435889894])  # cosine approximately 0.90
    d = m.compare("X", "Y")
    assert d.kind == "ambiguous"
    assert d.macro_concept is None
