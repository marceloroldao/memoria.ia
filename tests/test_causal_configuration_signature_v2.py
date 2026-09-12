from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.causal_configuration_signature_v2 import causal_configuration_signature
from memoria_resolutiva.causal_state_v2 import CausalStateSnapshot, VersionedCausalState


def _memory() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("lp1", "train:a", "train:b", "future:x", "ls1"))
    memory.ingest_address_stream(("lp2", "train:a", "train:b", "future:x", "ls2"))
    memory.ingest_address_stream(("hp1", "held:a", "held:b"))
    memory.ingest_address_stream(("hp2", "held:a", "held:b"))
    memory.ingest_address_stream(("ta1", "train:a", "tb1"))
    memory.ingest_address_stream(("ta2", "train:a", "tb2"))
    memory.ingest_address_stream(("ha1", "held:a", "hb1"))
    memory.ingest_address_stream(("ha2", "held:a", "hb2"))
    return memory


def test_causal_signature_matches_disjoint_regions_without_future_leakage():
    memory = _memory()
    learned = causal_configuration_signature(memory, ("train:a", "train:b"))
    held = causal_configuration_signature(memory, ("held:a", "held:b"))
    assert learned.supported is True
    assert held.supported is True
    assert learned.signature_id == held.signature_id


def test_versioned_causal_snapshot_is_not_rewritten_by_later_ingestion():
    memory = _memory()
    snapshot = CausalStateSnapshot.capture(memory)
    state = VersionedCausalState(snapshot, ("held:a", "held:b"))
    before = state.signature()

    # These later observations contain the old prefix plus new futures. They are
    # new evidence and are allowed to change the *live* memory, but they must not
    # rewrite the evidence universe that produced the historical causal state.
    memory.ingest_address_stream(("hp3", "held:a", "held:b", "new:future"))
    memory.ingest_address_stream(("hp4", "held:a", "held:b", "another:future"))

    historical_after = state.signature()
    live_after = causal_configuration_signature(memory, ("held:a", "held:b"))

    assert before.supported is True
    assert historical_after == before
    assert snapshot.revision == 8
    assert len(snapshot.trajectories) == 8
    assert len(memory.snapshot()) == 10
    # The live signature may change because the support geometry itself changed.
    assert live_after.supported is True


def test_causal_signature_rejects_reverse_order_without_reverse_support():
    memory = _memory()
    reverse = causal_configuration_signature(memory, ("train:b", "train:a"))
    assert reverse.supported is False
    assert reverse.reason == "insufficient-transition-support"


def test_causal_signature_fails_closed_on_hyperdense_predecessor_region():
    memory = AddressTrajectoryMemory()
    for i in range(40):
        memory.ingest_address_stream((f"p:{i}", "hub"))
    result = causal_configuration_signature(memory, ("hub",), max_predecessor_diversity=32)
    assert result.supported is False
    assert result.reason == "non-discriminative-causal-role"
