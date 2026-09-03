from benchmarks.layered_scale import build_balanced_graph


def _apply_full_reference(target_nodes: int, updates: dict[str, float]):
    graph, _, _ = build_balanced_graph(target_nodes)
    for node_id, value in updates.items():
        node = graph.nodes[node_id]
        node.value = value
        node.history.append(value)
    graph.full_recompute()
    return graph.snapshot()


def test_adaptive_policy_uses_incremental_for_sparse_change():
    graph, _, _ = build_balanced_graph(1_000)
    decision = graph.update_roots_adaptive({"r0": -1.0}, full_threshold=0.25)

    assert decision.mode == "incremental"
    assert decision.affected_fraction < 0.25
    assert len(decision.touched) < len(graph.nodes)
    assert graph.snapshot() == _apply_full_reference(1_000, {"r0": -1.0})


def test_adaptive_policy_uses_full_for_dense_change():
    graph, _, _ = build_balanced_graph(100)
    roots = [node_id for node_id, node in graph.nodes.items() if not node.parents]
    updates = {node_id: -(idx + 1.0) for idx, node_id in enumerate(roots)}

    decision = graph.update_roots_adaptive(updates, full_threshold=0.50)

    assert decision.mode == "full"
    assert decision.affected_fraction >= 0.50
    assert len(decision.touched) == len(graph.nodes)
    assert graph.snapshot() == _apply_full_reference(100, updates)


def test_adaptive_policy_rejects_invalid_threshold():
    graph, _, _ = build_balanced_graph(100)

    for threshold in (0.0, -0.1, 1.1):
        try:
            graph.update_roots_adaptive({"r0": -1.0}, full_threshold=threshold)
        except ValueError:
            pass
        else:
            raise AssertionError(f"threshold {threshold} should be rejected")
