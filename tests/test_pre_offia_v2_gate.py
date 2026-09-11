from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.end_to_end_resolver_v2 import EndToEndAddressResolver


def _transfer_memory() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()

    # Learned region: same ordered structural configuration reaches the same future
    # through two independent trajectories.
    memory.ingest_address_stream(("lp1", "train:a", "train:b", "future:x", "ls1"))
    memory.ingest_address_stream(("lp2", "train:a", "train:b", "future:x", "ls2"))

    # Held-out region: the configuration itself is independently observed, but its
    # frontier is intentionally absent. Any answer therefore has to come from the
    # anonymous structural fallback rather than exact contiguous recall.
    memory.ingest_address_stream(("hp1", "held:a", "held:b"))
    memory.ingest_address_stream(("hp2", "held:a", "held:b"))

    # Balance anonymous local-role geometry across the two literal spaces.
    memory.ingest_address_stream(("ta1", "train:a", "tb1"))
    memory.ingest_address_stream(("ta2", "train:a", "tb2"))
    memory.ingest_address_stream(("ha1", "held:a", "hb1"))
    memory.ingest_address_stream(("ha2", "held:a", "hb2"))
    return memory


def test_pre_offia_direct_recall_is_still_primary():
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma")
    result = EndToEndAddressResolver(memory, enable_structural_fallback=True).resolve_text("alpha beta")
    assert result.resolved is True
    assert result.source == "direct-contiguous-frontier"
    assert result.surface == "gamma"


def test_pre_offia_structural_transfer_produces_real_novel_recall():
    memory = _transfer_memory()
    result = EndToEndAddressResolver(memory, enable_structural_fallback=True).resolve_addresses(("held:a", "held:b"))
    assert result.resolved is True
    assert result.ambiguous is False
    assert result.source == "anonymous-structural-frontier"
    assert result.address == "future:x"
    assert len(result.supporting_trajectories) >= 2


def test_pre_offia_structural_transfer_survives_cold_restart_exactly():
    memory = _transfer_memory()
    before_snapshot = memory.snapshot()
    before = EndToEndAddressResolver(memory, enable_structural_fallback=True).resolve_addresses(("held:a", "held:b"))

    restored = AddressTrajectoryMemory.restore(before_snapshot)
    after = EndToEndAddressResolver(restored, enable_structural_fallback=True).resolve_addresses(("held:a", "held:b"))

    assert before == after
    assert restored.snapshot() == before_snapshot


def test_pre_offia_shared_hub_never_crosses_occurrence():
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("a", "hub", "x"))
    memory.ingest_address_stream(("b", "hub", "y"))
    result = EndToEndAddressResolver(memory, enable_structural_fallback=True).resolve_addresses(("a", "hub"))
    assert result.resolved is True
    assert result.address == "x"
    assert "y" not in result.competing_addresses


def test_pre_offia_multimodal_addresses_use_the_same_engine():
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("camera:shape:01", "imu:turn:02", "motor:state:03"))
    result = EndToEndAddressResolver(memory, enable_structural_fallback=True).resolve_addresses(("camera:shape:01", "imu:turn:02"))
    assert result.resolved is True
    assert result.address == "motor:state:03"
