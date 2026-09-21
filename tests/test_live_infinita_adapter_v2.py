from memoria_resolutiva.live_infinita_adapter_v2 import (
    make_live_request,
    to_world_state_candidates,
)


def test_live_adapter_normalizes_without_semantic_types():
    request = make_live_request(
        frame_id="frame-1",
        state_addresses=("live:a", "live:a", "live:b"),
        intervention_id="action-1",
        intervention_address="live:act",
        candidates=(
            ("cand-b", ("live:y",), ("live:a", "live:y")),
            ("cand-a", ("live:x",), ("live:a", "live:x")),
        ),
    )
    assert request.state.state_addresses == ("live:a", "live:b")
    assert tuple(item.candidate_id for item in request.candidates) == ("cand-a", "cand-b")


def test_live_adapter_converts_candidates_without_mutation():
    request = make_live_request(
        frame_id="frame-1",
        state_addresses=("s0", "s1"),
        intervention_id="i1",
        intervention_address="a0",
        candidates=(("c1", ("k0",), ("s0", "k0")),),
    )
    candidates = to_world_state_candidates(request)
    assert len(candidates) == 1
    assert candidates[0].candidate_id == "c1"
    assert candidates[0].consequence_addresses == ("k0",)
    assert candidates[0].next_state_addresses == ("s0", "k0")


def test_duplicate_candidate_ids_fail_closed():
    try:
        make_live_request(
            frame_id="frame-1",
            state_addresses=("s0",),
            intervention_id="i1",
            intervention_address="a0",
            candidates=(
                ("dup", ("x",), ("x",)),
                ("dup", ("y",), ("y",)),
            ),
        )
    except ValueError as exc:
        assert "candidate_id" in str(exc)
    else:
        raise AssertionError("duplicate candidate ids must fail closed")


def test_empty_addresses_fail_closed():
    for kwargs in (
        dict(frame_id="", state_addresses=("s",), intervention_id="i", intervention_address="a"),
        dict(frame_id="f", state_addresses=(), intervention_id="i", intervention_address="a"),
        dict(frame_id="f", state_addresses=("s",), intervention_id="", intervention_address="a"),
        dict(frame_id="f", state_addresses=("s",), intervention_id="i", intervention_address=""),
    ):
        try:
            make_live_request(candidates=(), **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid live request must fail closed")


def test_transport_order_does_not_change_normalized_candidate_order():
    a = make_live_request(
        frame_id="f",
        state_addresses=("s0", "s1"),
        intervention_id="i",
        intervention_address="a",
        candidates=(
            ("z", ("z",), ("s0", "z")),
            ("a", ("a",), ("s0", "a")),
        ),
    )
    b = make_live_request(
        frame_id="f",
        state_addresses=("s0", "s1"),
        intervention_id="i",
        intervention_address="a",
        candidates=(
            ("a", ("a",), ("s0", "a")),
            ("z", ("z",), ("s0", "z")),
        ),
    )
    assert a == b
