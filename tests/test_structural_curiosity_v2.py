from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.cognitive_cycle_v2 import CognitiveCycleV2
from memoria_resolutiva.structural_curiosity_v2 import derive_curiosity


def _memory() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("a", "b", "c", "d"))
    memory.ingest_address_stream(("a", "b", "c", "omega"))
    return memory


def test_curiosity_waits_through_shared_future_and_targets_first_real_divergence():
    prediction = CognitiveCycleV2(_memory()).predict_addresses(("a", "b"))
    probe = derive_curiosity(prediction.branches)

    assert probe.needed is True
    assert probe.reason == "branch-divergence"
    assert probe.divergence_depth == 1
    assert probe.alternative_addresses == ("d", "omega")
    assert probe.unresolved_branches == 2


def test_curiosity_disappears_after_observation_selects_one_branch():
    cycle = CognitiveCycleV2(_memory())
    prediction = cycle.predict_addresses(("a", "b"))
    correction = cycle.correct_addresses(prediction, ("c", "d"))
    probe = derive_curiosity(correction.corrected)

    assert probe.needed is False
    assert probe.reason == "single-active-branch"


def test_identical_future_branches_do_not_manufacture_curiosity():
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("a", "b", "c", "d"))
    memory.ingest_address_stream(("a", "b", "c", "d"))
    prediction = CognitiveCycleV2(memory).predict_addresses(("a", "b"))
    probe = derive_curiosity(prediction.branches)

    assert probe.needed is False


def test_terminal_vs_continuing_branch_is_a_real_discriminator():
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("a", "b", "c"))
    memory.ingest_address_stream(("a", "b", "c", "d"))
    prediction = CognitiveCycleV2(memory).predict_addresses(("a", "b"))
    probe = derive_curiosity(prediction.branches)

    assert probe.needed is True
    assert probe.divergence_depth == 1
    assert "<END>" in probe.alternative_addresses
    assert "d" in probe.alternative_addresses


def test_curiosity_is_deterministic_after_restart():
    memory = _memory()
    probe1 = derive_curiosity(CognitiveCycleV2(memory).predict_addresses(("a", "b")).branches)
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    probe2 = derive_curiosity(CognitiveCycleV2(restored).predict_addresses(("a", "b")).branches)
    assert probe1 == probe2
