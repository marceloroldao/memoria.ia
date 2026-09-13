from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.cognitive_cycle_v2 import CognitiveCycleV2
from memoria_resolutiva.prediction_error_v2 import classify_prediction_error


def _memory() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("a", "b", "c", "d"))
    memory.ingest_address_stream(("a", "b", "c", "omega"))
    return memory


def test_prediction_confirmed_is_zero_structural_loss_class():
    memory = _memory()
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ("c",))
    error = classify_prediction_error(prediction, correction)

    assert error.kind == "prediction-confirmed"
    assert error.predicted_branches == 2
    assert error.surviving_branches == 2
    assert error.eliminated_branches == 0
    assert error.observation_depth == 1
    assert error.surprising is False


def test_branch_reduction_is_recorded_without_becoming_surprise():
    memory = _memory()
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ("c", "d"))
    error = classify_prediction_error(prediction, correction)

    assert error.kind == "hypothesis-reduction"
    assert error.predicted_branches == 2
    assert error.surviving_branches == 1
    assert error.eliminated_branches == 1
    assert error.observation_depth == 2
    assert error.surprising is False


def test_total_exhaustion_is_total_surprise():
    memory = _memory()
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ("z",))
    error = classify_prediction_error(prediction, correction)

    assert error.kind == "total-surprise"
    assert error.predicted_branches == 2
    assert error.surviving_branches == 0
    assert error.eliminated_branches == 2
    assert error.surprising is True


def test_no_prediction_is_not_mislabeled_as_surprise():
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("a", "b"))
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ("x",))
    error = classify_prediction_error(prediction, correction)

    assert error.kind == "unconstrained-observation"
    assert error.predicted_branches == 0
    assert error.surviving_branches == 0
    assert error.surprising is False


def test_error_classification_is_restart_deterministic():
    memory = _memory()
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ("c", "omega"))
    first = classify_prediction_error(prediction, correction)

    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    cycle2 = CognitiveCycleV2(restored)
    prediction2 = cycle2.predict_addresses(("a", "b"))
    correction2 = cycle2.correct_addresses(prediction2, ("c", "omega"))
    second = classify_prediction_error(prediction2, correction2)

    assert first == second
