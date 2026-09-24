import hashlib
import json

import pytest

from memoria_resolutiva.bit_analyze_convergence_v2 import (
    BIT_ANALYZE_REALITY_SLICE_SCHEMA,
    BitAnalyzeConvergenceV2,
    RealitySliceObservationStoreV2,
)
from memoria_resolutiva.resolutive_inference_v2 import ResolutiveInferenceEngineV2
from memoria_resolutiva.structural_observation import StructuralObservationStore
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _slice(*, slice_id=7, trail=(21, 22, 23)):
    occurrences = [
        {
            "pattern": pattern,
            "dt_start": index * 0.1,
            "dt_end": index * 0.1 + 0.05,
            "source": index + 1,
            "provenance": 100 + index,
        }
        for index, pattern in enumerate(trail)
    ]
    core = {
        "schema": BIT_ANALYZE_REALITY_SLICE_SCHEMA,
        "source_id": "camera-audio-fusion",
        "slice_id": slice_id,
        "trail": list(trail),
        "occurrences": occurrences,
        "slice_provenance": [501, 502],
        "temporal": {
            "clock_id": "monotonic:lab",
            "t_start": 100.0,
            "t_end": 100.5,
            "unit": "s",
        },
        "semantic_projection": False,
    }
    core["signature"] = hashlib.blake2b(_canonical(core), digest_size=20).hexdigest()
    return core


def _event():
    return {
        "version": 1,
        "source_id": "raw-byte-stream",
        "sequence": 3,
        "byte_offset": 256,
        "byte_length": 128,
        "trail": [11, 12, 13],
        "relation_ids": [71, 72],
        "signature": "0123456789abcdef",
        "resolution": 2,
    }


def _runtime(tmp_path):
    events = StructuralObservationStore(
        tmp_path / "events",
        backend="sqlite",
        allow_fallback=False,
    )
    slices = RealitySliceObservationStoreV2(
        tmp_path / "slices",
        backend="sqlite",
        allow_fallback=False,
    )
    index = StructuralTrajectoryIndex()
    return BitAnalyzeConvergenceV2(
        structural_events=events,
        reality_slices=slices,
        trajectories=index,
    )


def test_r13_structural_event_and_reality_slice_converge_only_at_trajectory_layer(tmp_path):
    runtime = _runtime(tmp_path)
    event_envelope, event_trajectory, _ = runtime.ingest_structural_event(
        _event(),
        hierarchy_id="world",
        provenance={"capture_id": "capture:raw"},
    )
    slice_envelope, slice_trajectory, _ = runtime.ingest_reality_slice(
        _slice(),
        hierarchy_id="world",
    )

    assert event_envelope["event"]["byte_offset"] == 256
    assert "byte_offset" not in slice_envelope["structural_slice"]
    assert slice_envelope["structural_slice"]["temporal"]["clock_id"] == "monotonic:lab"
    assert event_trajectory.addresses == (11, 12, 13)
    assert slice_trajectory.addresses == (21, 22, 23)
    assert runtime.trajectories.count == 2

    result = ResolutiveInferenceEngineV2(runtime.trajectories).infer_structural(
        [21, 22],
        hierarchy_id="world",
    )
    assert result.status == "resolved"
    assert result.resolved_address == 23
    assert result.diagnostics.llm_calls == 0


def test_r13_reality_slice_preserves_timing_multiplicity_and_provenance_without_modality_law(tmp_path):
    runtime = _runtime(tmp_path)
    envelope, _, _ = runtime.ingest_reality_slice(
        _slice(trail=(21, 21, 22)),
        hierarchy_id="world",
    )
    stored = runtime.reality_slices.get(envelope["observation_id"])
    row = stored["structural_slice"]

    assert row["trail"] == [21, 21, 22]
    assert row["occurrences"][0]["dt_start"] == 0.0
    assert row["occurrences"][1]["provenance"] == 101
    assert row["slice_provenance"] == [501, 502]
    assert all("modality" not in occurrence for occurrence in row["occurrences"])
    assert row["semantic_projection"] is False


def test_r13_reality_slice_signature_is_verified_before_memory_admission(tmp_path):
    runtime = _runtime(tmp_path)
    tampered = _slice()
    tampered["occurrences"][0]["dt_end"] = 0.49

    with pytest.raises(ValueError, match="signature mismatch"):
        runtime.ingest_reality_slice(tampered, hierarchy_id="world")

    assert runtime.reality_slices.count == 0
    assert runtime.trajectories.count == 0


def test_r13_duplicate_ingest_and_cold_replay_are_idempotent(tmp_path):
    runtime = _runtime(tmp_path)
    first_event = runtime.ingest_structural_event(_event(), hierarchy_id="world")
    second_event = runtime.ingest_structural_event(_event(), hierarchy_id="world")
    first_slice = runtime.ingest_reality_slice(_slice(), hierarchy_id="world")
    second_slice = runtime.ingest_reality_slice(_slice(), hierarchy_id="world")

    assert first_event[1] == second_event[1]
    assert first_slice[1] == second_slice[1]
    assert second_event[2] is True
    assert second_slice[2] is True
    assert runtime.trajectories.count == 2

    reopened = _runtime(tmp_path)
    assert reopened.trajectories.count == 0
    assert reopened.replay() == 2
    assert reopened.replay() == 0
    assert reopened.trajectories.snapshot() == runtime.trajectories.snapshot()
