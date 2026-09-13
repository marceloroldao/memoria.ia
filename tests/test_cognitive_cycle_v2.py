from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.cognitive_cycle_v2 import CognitiveCycleV2


def _branching_memory() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("a", "b", "c", "d"))
    memory.ingest_address_stream(("a", "b", "c", "omega"))
    return memory


def test_prediction_is_anchored_to_historical_snapshot():
    memory = _branching_memory()
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    revision = prediction.state.snapshot.revision
    original_snapshot = prediction.state.snapshot.trajectories

    memory.ingest_address_stream(("a", "b", "new"))

    assert prediction.state.snapshot.revision == revision
    assert prediction.state.snapshot.trajectories == original_snapshot
    assert prediction.state.snapshot.revision != len(memory.snapshot())


def test_matching_observation_confirms_prediction_without_mutating_memory():
    memory = _branching_memory()
    before = memory.snapshot()
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ("c",))

    assert correction.outcome == "confirmed"
    assert correction.surprising is False
    assert correction.corrected.exhausted is False
    assert memory.snapshot() == before


def test_later_observation_reduces_competing_branches():
    memory = _branching_memory()
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    after_shared = cycle.correct_addresses(prediction, ("c",))

    # The first shared continuation keeps both futures alive.
    assert len(after_shared.corrected.active) == 2

    # Correct from the original prediction with both observations in sequence.
    after_delta = cycle.correct_addresses(prediction, ("c", "d"))
    assert after_delta.outcome == "branch-reduction"
    assert after_delta.corrected.exhausted is False
    assert len(after_delta.corrected.active) == 1


def test_unexpected_observation_exhausts_and_marks_surprise():
    memory = _branching_memory()
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ("z",))

    assert correction.outcome == "exhausted"
    assert correction.surprising is True
    assert correction.corrected.exhausted is True


def test_exhaustion_can_recover_from_known_other_region_without_stitching():
    memory = _branching_memory()
    memory.ingest_address_stream(("z", "y", "q"))
    cycle = CognitiveCycleV2(memory)
    before = memory.snapshot()

    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ("z",))
    recovered = cycle.recover(correction)

    assert recovered.recovery.recovered_any is True
    assert recovered.recovery.recovered.exhausted is False
    assert all("AT1" not in branch.trajectory_ids and "AT2" not in branch.trajectory_ids for branch in recovered.recovery.recovered.active)
    assert recovered.next_state.snapshot.revision == len(before)
    assert memory.snapshot() == before


def test_cold_restart_preserves_prediction_and_correction():
    memory = _branching_memory()
    prediction = CognitiveCycleV2(memory).predict_addresses(("a", "b"))
    correction = CognitiveCycleV2(memory).correct_addresses(prediction, ("c", "omega"))

    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    prediction2 = CognitiveCycleV2(restored).predict_addresses(("a", "b"))
    correction2 = CognitiveCycleV2(restored).correct_addresses(prediction2, ("c", "omega"))

    assert prediction == prediction2
    assert correction == correction2


def test_no_prediction_does_not_call_observation_an_error():
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("a", "b"))
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ("x",))

    assert prediction.has_prediction is False
    assert correction.outcome == "no-prediction"
    assert correction.surprising is False
