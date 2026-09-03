from memoria_resolutiva.incremental_recompute import IncrementalRecomputeGraph


def build_graph():
    g = IncrementalRecomputeGraph()
    g.add_root("R1", 1.0)
    g.add_root("R2", 0.4)
    g.add_derived("A", ["R1"])
    g.add_derived("B", ["A"])
    g.add_derived("C", ["B", "R2"])
    g.add_derived("U", ["R2"])
    return g


def test_incremental_matches_full_recompute():
    g = build_graph()
    g.update_root_incremental("R1", 0.2)
    inc = g.snapshot()
    g.full_recompute()
    assert g.snapshot() == inc


def test_unaffected_branch_is_not_touched_incrementally():
    g = build_graph()
    touched = set(g.update_root_incremental("R1", 0.2))
    assert touched == {"R1", "A", "B", "C"}
    assert "U" not in touched and "R2" not in touched


def test_full_recompute_touches_all_nodes():
    g = build_graph()
    touched = set(g.full_recompute())
    assert touched == {"R1", "R2", "A", "B", "C", "U"}


def test_history_preserves_old_and_new_values():
    g = build_graph()
    old = g.nodes["A"].value
    g.update_root_incremental("R1", 0.2)
    assert g.nodes["A"].history[0] == old
    assert g.nodes["A"].history[-1] == 0.2


def test_each_derived_node_can_keep_its_own_rule():
    g = IncrementalRecomputeGraph()
    g.add_root("x", 2.0)
    g.add_root("y", 3.0)
    g.add_derived("sum", ["x", "y"], combine=sum)
    g.add_derived("product", ["x", "y"], combine=lambda xs: xs[0] * xs[1])
    assert g.snapshot()["sum"] == 5.0
    assert g.snapshot()["product"] == 6.0

    g.update_root_incremental("x", 4.0)
    assert g.snapshot()["sum"] == 7.0
    assert g.snapshot()["product"] == 12.0


def test_cycle_detection_is_explicit():
    g = build_graph()
    # Artificial corruption only for regression of cycle detection.
    g.nodes["R1"].parents = ("C",)
    g.children.setdefault("C", set()).add("R1")
    try:
        g.full_recompute()
    except ValueError as exc:
        assert "cycle" in str(exc)
    else:
        raise AssertionError("cycle should be rejected")
