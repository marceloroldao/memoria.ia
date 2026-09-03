from benchmarks.layered_scale import build_balanced_graph


def _set_roots_direct(graph, updates):
    for node_id, value in updates.items():
        node = graph.nodes[node_id]
        node.value = value
        node.history.append(value)


def test_batched_updates_match_full_recompute():
    graph, _, _ = build_balanced_graph(1_000)
    updates = {"r0": -1.0, "r511": -2.0}
    touched = graph.update_roots_incremental(updates)
    incremental_snapshot = graph.snapshot()

    full_graph, _, _ = build_balanced_graph(1_000)
    _set_roots_direct(full_graph, updates)
    full_graph.full_recompute()

    assert incremental_snapshot == full_graph.snapshot()
    assert len(touched) < len(full_graph.nodes)


def test_shared_descendants_are_touched_once_per_batch():
    graph, _, _ = build_balanced_graph(100)
    touched = graph.update_roots_incremental({"r0": -1.0, "r1": -2.0})

    assert len(touched) == len(set(touched))
    assert "r0" in touched and "r1" in touched
    # r0 and r1 converge immediately, so batching should avoid recomputing the
    # shared ancestor chain twice.
    assert len(touched) < 2 * 8


def test_empty_batch_is_noop():
    graph, _, _ = build_balanced_graph(100)
    before = graph.snapshot()
    assert graph.update_roots_incremental({}) == []
    assert graph.snapshot() == before
