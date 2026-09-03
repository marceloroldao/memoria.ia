from benchmarks.layered_scale import build_balanced_graph
from memoria_resolutiva.adaptive_recompute import HysteresisRecomputePolicy


def _updates(count: int, value: float) -> dict[str, float]:
    return {f"r{i}": value - i for i in range(count)}


def test_hysteresis_prevents_ping_pong_near_boundary():
    graph, _, _ = build_balanced_graph(100)
    policy = HysteresisRecomputePolicy(
        enter_full_threshold=0.50,
        exit_full_threshold=0.30,
    )

    sparse = policy.apply(graph, _updates(1, -10.0))
    assert sparse.mode == "incremental"

    dense = policy.apply(graph, _updates(32, -20.0))
    assert dense.mode == "full"

    # A medium-density batch below the enter threshold does not immediately
    # switch back because it is still above the lower exit threshold.
    medium = policy.apply(graph, _updates(16, -30.0))
    assert medium.mode == "full"

    sparse_again = policy.apply(graph, _updates(1, -40.0))
    assert sparse_again.mode == "incremental"


def test_hysteresis_modes_match_full_reference_snapshots():
    graph, _, _ = build_balanced_graph(1_000)
    reference, _, _ = build_balanced_graph(1_000)
    policy = HysteresisRecomputePolicy(
        enter_full_threshold=0.40,
        exit_full_threshold=0.20,
    )

    batches = [
        _updates(1, -10.0),
        _updates(256, -20.0),
        _updates(64, -30.0),
        _updates(1, -40.0),
    ]
    for batch in batches:
        policy.apply(graph, batch)
        reference._apply_root_updates(batch)
        reference.full_recompute()
        assert graph.snapshot() == reference.snapshot()


def test_hysteresis_rejects_invalid_thresholds_and_mode():
    for enter, exit_ in ((0.5, 0.5), (0.4, 0.6), (1.1, 0.2), (0.5, 0.0)):
        try:
            HysteresisRecomputePolicy(enter_full_threshold=enter, exit_full_threshold=exit_)
        except ValueError:
            pass
        else:
            raise AssertionError((enter, exit_))

    try:
        HysteresisRecomputePolicy(mode="other")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid mode accepted")
