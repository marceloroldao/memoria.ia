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
