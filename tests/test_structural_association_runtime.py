from __future__ import annotations

from memoria_resolutiva.structural_association_runtime import StructuralAssociationRuntime
from memoria_resolutiva.structural_observation import StructuralObservationStore


def _event(sequence: int, trail: list[int]) -> dict:
    return {
        "version": 1,
        "source_id": "web:test",
        "sequence": sequence,
        "byte_offset": sequence * 16,
        "byte_length": 16,
        "trail": trail,
        "relation_ids": [item for item in trail if item >= 256],
        "signature": f"{sequence + 1:016x}",
        "resolution": 2,
    }


def _append(store: StructuralObservationStore, sequence: int, trail: list[int]):
    return store.append(
        _event(sequence, trail),
        provenance={
            "hierarchy_id": "hierarchy:test",
            "capture_id": f"capture:{sequence}",
        },
    )[0]


def test_runtime_restart_preserves_exact_derived_state_and_cursor(tmp_path):
    raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    _append(raw, 0, [1, 2, 300])
    _append(raw, 1, [2, 3, 301])
    _append(raw, 2, [1, 2, 300])

    runtime = StructuralAssociationRuntime(
        raw,
        tmp_path / "derived",
        backend="sqlite",
        allow_fallback=False,
        max_within_distance=3,
        max_event_lag=2,
        forgetting_rate=0.03,
    )
    before = runtime.snapshot()
    assert before["cursor"]["count"] == 3
    assert before["pending_observations"] == 0
    assert before["field"]["observations"] == 3
    assert before["field"]["edges"]

    restarted_raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    restarted = StructuralAssociationRuntime(
        restarted_raw,
        tmp_path / "derived",
        backend="sqlite",
        allow_fallback=False,
        max_within_distance=99,
        max_event_lag=99,
        forgetting_rate=0.99,
    )
    after = restarted.snapshot()

    assert after["replayed_on_open"] == 0
    assert after["cursor"] == before["cursor"]
    assert after["field"] == before["field"]
    assert after["field"]["max_within_distance"] == 3
    assert after["field"]["max_event_lag"] == 2
    assert after["field"]["forgetting_rate"] == 0.03


def test_runtime_replays_only_raw_suffix_left_after_crash(tmp_path):
    raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    _append(raw, 0, [10])
    _append(raw, 1, [20])

    runtime = StructuralAssociationRuntime(
        raw,
        tmp_path / "derived",
        backend="sqlite",
        allow_fallback=False,
        max_event_lag=1,
        forgetting_rate=0,
    )
    assert runtime.cursor_count == 2
    baseline = runtime.field.association(
        "hierarchy:test",
        10,
        20,
        channel="temporal",
    )
    assert baseline == 1.0

    # Simulate a crash window: raw observation committed, derived runtime not synced.
    _append(raw, 2, [30])

    restarted_raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    restarted = StructuralAssociationRuntime(
        restarted_raw,
        tmp_path / "derived",
        backend="sqlite",
        allow_fallback=False,
    )

    assert restarted.replayed_on_open == 1
    assert restarted.cursor_count == 3
    assert restarted.snapshot()["pending_observations"] == 0
    assert restarted.field.association(
        "hierarchy:test",
        10,
        20,
        channel="temporal",
    ) == baseline
    assert restarted.field.association(
        "hierarchy:test",
        20,
        30,
        channel="temporal",
    ) > 0.0


def test_runtime_second_restart_does_not_reinforce_replayed_suffix_again(tmp_path):
    raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    _append(raw, 0, [7])
    first = StructuralAssociationRuntime(
        raw,
        tmp_path / "derived",
        backend="sqlite",
        allow_fallback=False,
        max_event_lag=1,
        forgetting_rate=0,
    )
    assert first.cursor_count == 1

    _append(raw, 1, [8])

    raw_after_crash = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    recovered = StructuralAssociationRuntime(
        raw_after_crash,
        tmp_path / "derived",
        backend="sqlite",
        allow_fallback=False,
    )
    weight = recovered.field.association(
        "hierarchy:test",
        7,
        8,
        channel="temporal",
    )
    assert recovered.replayed_on_open == 1
    assert weight == 1.0

    raw_again = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    restarted_again = StructuralAssociationRuntime(
        raw_again,
        tmp_path / "derived",
        backend="sqlite",
        allow_fallback=False,
    )
    assert restarted_again.replayed_on_open == 0
    assert restarted_again.field.association(
        "hierarchy:test",
        7,
        8,
        channel="temporal",
    ) == weight
    assert restarted_again.field.snapshot()["observations"] == 2
