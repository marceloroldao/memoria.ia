from memoria_resolutiva.correction_propagation import CorrectionGraph


def build_graph():
    g = CorrectionGraph()
    g.add_node("r1", "root1")
    g.add_node("r2", "root2")
    g.add_node("a", "A", parents={"r1"})
    g.add_node("b", "B", parents={"a", "r2"})
    g.add_node("c", "C", parents={"b"})
    g.add_node("u", "U", parents={"r2"})
    return g


def test_only_descendants_are_affected():
    g = build_graph()
    affected = set(g.correct("r1", "root1-corrected"))
    assert affected == {"a", "b", "c"}
    assert "u" not in affected


def test_correction_preserves_history():
    g = build_graph()
    g.correct("r1", "new")
    node = g.nodes["r1"]
    assert node.version == 1
    assert node.history and node.history[0][1] == "root1"
    assert node.value == "new"


def test_invalidation_marks_root_inactive_and_returns_affected_subgraph():
    g = build_graph()
    affected = set(g.invalidate("r1"))
    assert not g.nodes["r1"].active
    assert affected == {"a", "b", "c"}


def test_lineage_is_transitive():
    g = build_graph()
    assert g.lineage("c") == {"b", "a", "r1", "r2"}


def test_unrelated_root_has_different_local_impact():
    g = build_graph()
    affected = set(g.correct("r2", "root2-corrected"))
    assert affected == {"b", "c", "u"}
    assert "a" not in affected
