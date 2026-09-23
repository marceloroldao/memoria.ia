from __future__ import annotations

from pathlib import Path

import pytest

from memoria_resolutiva.bdr_store import native_bdr_available
from memoria_resolutiva.persistent_structural_trajectory_v2 import (
    PersistentStructuralTrajectoryRuntimeV2,
)
from memoria_resolutiva.structural_observation import StructuralObservationStore


def _event(sequence: int, trail: list[int], *, source_id: str = "sensor") -> dict:
    return {
        "version": 1,
        "source_id": source_id,
        "sequence": sequence,
        "byte_offset": sequence * 16,
        "byte_length": 16,
        "trail": trail,
        "relation_ids": [],
        "signature": f"{sequence + 1:016x}",
        "resolution": 2,
    }


def _append(store: StructuralObservationStore, sequence: int, trail: list[int], *, hierarchy: str = "h"):
    return store.append(
        _event(sequence, trail),
        provenance={"hierarchy_id": hierarchy, "source_kind": "test"},
    )[0]


def test_structural_trajectory_checkpoint_survives_cold_reopen(tmp_path: Path):
    observations = StructuralObservationStore(
        tmp_path / "observations",
        backend="sqlite",
        allow_fallback=False,
    )
    _append(observations, 0, [1, 2, 3])
    _append(observations, 1, [1, 2, 4])

    first = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    before = first.snapshot_bytes()
    assert first.status()["trajectories"] == 2
    assert first.frontier([1, 2], hierarchy_id="h").ambiguous is True

    restarted = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    assert restarted.replayed_on_open == 0
    assert restarted.snapshot_bytes() == before
    assert restarted.status()["backend"] == "sqlite"
    assert restarted.frontier([3], hierarchy_id="h", direction="reverse").resolved_address == 2


def test_cold_reopen_replays_only_raw_suffix_missing_from_checkpoint(tmp_path: Path):
    observations = StructuralObservationStore(
        tmp_path / "observations",
        backend="sqlite",
        allow_fallback=False,
    )
    _append(observations, 0, [10, 20])

    first = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    assert first.status()["cursor"]["count"] == 1

    # Simulate a raw observation committed after the last trajectory checkpoint.
    second_envelope = _append(observations, 1, [20, 30])

    restarted = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    assert restarted.replayed_on_open == 1
    assert restarted.status()["cursor"] == {
        "count": 2,
        "observation_id": second_envelope["observation_id"],
    }
    assert restarted.status()["pending_observations"] == 0
    assert restarted.status()["trajectories"] == 2


def test_trajectory_query_is_read_only_across_persistent_runtime(tmp_path: Path):
    observations = StructuralObservationStore(
        tmp_path / "observations",
        backend="sqlite",
        allow_fallback=False,
    )
    _append(observations, 0, [7, 8, 9])
    runtime = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    before = runtime.snapshot_bytes()

    assert runtime.resolve_addresses([7, 8], hierarchy_id="h")
    assert runtime.frontier([8], hierarchy_id="h").resolved_address == 9

    assert runtime.snapshot_bytes() == before
    assert runtime.status()["raw_observations"] == 1


def test_trajectory_checkpoint_rejects_raw_prefix_mismatch(tmp_path: Path):
    observations = StructuralObservationStore(
        tmp_path / "observations-a",
        backend="sqlite",
        allow_fallback=False,
    )
    _append(observations, 0, [1, 2])
    PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )

    incompatible = StructuralObservationStore(
        tmp_path / "observations-b",
        backend="sqlite",
        allow_fallback=False,
    )
    _append(incompatible, 0, [9, 10])

    with pytest.raises(ValueError, match="cursor does not match raw observation prefix"):
        PersistentStructuralTrajectoryRuntimeV2(
            incompatible,
            tmp_path / "trajectory",
            backend="sqlite",
            allow_fallback=False,
        )


@pytest.mark.skipif(not native_bdr_available(), reason="native BDR extension not built")
def test_structural_trajectory_cold_reopen_on_native_bdr(tmp_path: Path):
    observations = StructuralObservationStore(
        tmp_path / "observations",
        backend="bdr",
        allow_fallback=False,
    )
    _append(observations, 0, [100, 200, 300])
    first = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="bdr",
        allow_fallback=False,
    )
    assert first.status()["backend"] == "bdr"

    restarted = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="bdr",
        allow_fallback=False,
    )
    assert restarted.replayed_on_open == 0
    assert restarted.index.snapshot() == first.index.snapshot()
