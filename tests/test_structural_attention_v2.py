from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.cognitive_cycle_v2 import CognitiveCycleV2
from memoria_resolutiva.prediction_error_v2 import classify_prediction_error
from memoria_resolutiva.structural_attention_v2 import derive_structural_attention


def _branching_memory() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("a", "b", "c", "d"))
    memory.ingest_address_stream(("a", "b", "c", "omega"))
    return memory


def _attention(observation: tuple[str, ...]):
    memory = _branching_memory()
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, observation)
    error = classify_prediction_error(prediction, correction)
    return derive_structural_attention(error)


def test_confirmed_prediction_stays_routine():
    attention = _attention(("c",))
    assert attention.level == "routine"
    assert attention.informative is False
    assert attention.requires_recovery is False
    assert attention.prediction_constrained is True


def test_branch_reduction_is_informative_without_recovery():
    attention = _attention(("c", "d"))
    assert attention.level == "informative"
    assert attention.reason == "observation-reduced-live-hypotheses"
    assert attention.informative is True
    assert attention.requires_recovery is False
    assert attention.eliminated_branches == 1


def test_total_surprise_requires_reorientation_and_recovery():
    attention = _attention(("z",))
    assert attention.level == "reorient"
    assert attention.reason == "all-predicted-branches-eliminated"
    assert attention.requires_recovery is True
    assert attention.informative is True
    assert attention.eliminated_branches == 2


def test_unconstrained_observation_is_not_false_surprise():
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("a", "b"))
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ("x",))
    error = classify_prediction_error(prediction, correction)
    attention = derive_structural_attention(error)

    assert attention.level == "informative"
    assert attention.reason == "observation-without-prior-prediction"
    assert attention.requires_recovery is False
    assert attention.prediction_constrained is False


def test_no_observation_stays_routine():
    memory = _branching_memory()
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ())
    error = classify_prediction_error(prediction, correction)
    attention = derive_structural_attention(error)

    assert attention.level == "routine"
    assert attention.informative is False
    assert attention.observation_depth == 0


def test_attention_is_deterministic_after_cold_restart():
    memory = _branching_memory()
    cycle = CognitiveCycleV2(memory)
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ("c", "d"))
    before = derive_structural_attention(classify_prediction_error(prediction, correction))

    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    cycle2 = CognitiveCycleV2(restored)
    prediction2 = cycle2.predict_addresses(("a", "b"))
    correction2 = cycle2.correct_addresses(prediction2, ("c", "d"))
    after = derive_structural_attention(classify_prediction_error(prediction2, correction2))

    assert before == after
