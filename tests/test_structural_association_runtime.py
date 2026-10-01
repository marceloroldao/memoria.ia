from __future__ import annotations

import json

from memoria_resolutiva.structural_association_field import StructuralAssociationField
from memoria_resolutiva.structural_association_runtime import (
    COMPACT_POINTER_FORMAT,
    POINTER_FORMAT,
    RUNTIME_FORMAT,
    StructuralAssociationPersistence,
    StructuralAssociationRuntime,
    _canonical_json,
)
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

def test_runtime_can_defer_replay_on_open_and_sync_later(tmp_path):
    raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    _append(raw, 0, [11])
    first = StructuralAssociationRuntime(
        raw,
        tmp_path / "derived",
        backend="sqlite",
        allow_fallback=False,
    )
    assert first.cursor_count == 1

    _append(raw, 1, [22])
    restarted_raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    deferred = StructuralAssociationRuntime(
        restarted_raw,
        tmp_path / "derived",
        backend="sqlite",
        allow_fallback=False,
        replay_on_open=False,
    )
    status = deferred.status()
    assert status["replay_on_open"] is False
    assert status["replayed_on_open"] == 0
    assert status["pending_observations"] == 1
    assert deferred.cursor_count == 1

    assert deferred.sync() == 1
    assert deferred.status()["pending_observations"] == 0
    assert deferred.cursor_count == 2

def test_runtime_sync_can_bound_pending_suffix(tmp_path):
    raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    for sequence in range(5):
        _append(raw, sequence, [sequence + 1])

    runtime = StructuralAssociationRuntime(
        raw,
        tmp_path / "derived",
        backend="sqlite",
        allow_fallback=False,
        replay_on_open=False,
    )
    assert runtime.cursor_count == 0
    assert runtime.sync(max_observations=2) == 2
    assert runtime.cursor_count == 2
    assert runtime.status()["pending_observations"] == 3
    assert runtime.sync(max_observations=2) == 2
    assert runtime.cursor_count == 4
    assert runtime.status()["pending_observations"] == 1
    assert runtime.sync(max_observations=2) == 1
    assert runtime.cursor_count == 5
    assert runtime.status()["pending_observations"] == 0

def test_runtime_compact_checkpoint_is_restart_safe_and_prunes_old_state(tmp_path):
    raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    for sequence in range(3):
        _append(raw, sequence, [sequence + 1, sequence + 10])

    derived = tmp_path / "derived"
    runtime = StructuralAssociationRuntime(
        raw,
        derived,
        backend="sqlite",
        allow_fallback=False,
        replay_on_open=False,
    )
    assert runtime.sync(max_observations=2) == 2

    pointer = json.loads((derived / "current.json").read_text("utf-8"))
    assert pointer["format"] == COMPACT_POINTER_FORMAT
    compact_files = list((derived / "compact-states").glob("*.json.zlib"))
    assert len(compact_files) == 1
    before = runtime.snapshot()

    restarted_raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    restarted = StructuralAssociationRuntime(
        restarted_raw,
        derived,
        backend="sqlite",
        allow_fallback=False,
        replay_on_open=False,
    )
    assert restarted.checkpoint_format == COMPACT_POINTER_FORMAT
    assert restarted.cursor_count == 2
    assert restarted.status()["pending_observations"] == 1
    assert restarted.field.snapshot() == before["field"]

    assert restarted.sync(max_observations=1) == 1
    compact_files_after = list((derived / "compact-states").glob("*.json.zlib"))
    assert len(compact_files_after) == 1
    assert restarted.cursor_count == 3
    assert restarted.status()["pending_observations"] == 0


def test_runtime_reads_legacy_pointer_and_migrates_on_next_checkpoint(tmp_path):
    raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    envelope = _append(raw, 0, [7, 8])
    field = StructuralAssociationField()
    field.observe(envelope)

    derived = tmp_path / "derived"
    derived.mkdir(parents=True)
    persistence = StructuralAssociationPersistence(
        derived / "persistence",
        backend="sqlite",
        allow_fallback=False,
    )
    payload = _canonical_json({
        "format": RUNTIME_FORMAT,
        "cursor": {
            "count": 1,
            "observation_id": envelope["observation_id"],
        },
        "field": field.export_state(),
    })
    receipt = persistence.store(payload)
    (derived / "current.json").write_text(
        json.dumps({
            "format": POINTER_FORMAT,
            "receipt": receipt.as_dict(),
            "cursor": {
                "count": 1,
                "observation_id": envelope["observation_id"],
            },
        }),
        encoding="utf-8",
    )

    loaded = StructuralAssociationRuntime(
        raw,
        derived,
        backend="sqlite",
        allow_fallback=False,
        replay_on_open=False,
    )
    assert loaded.checkpoint_format == POINTER_FORMAT
    assert loaded.cursor_count == 1

    _append(raw, 1, [8, 9])
    assert loaded.sync(max_observations=1) == 1
    migrated = json.loads((derived / "current.json").read_text("utf-8"))
    assert migrated["format"] == COMPACT_POINTER_FORMAT
    assert loaded.checkpoint_format == COMPACT_POINTER_FORMAT
