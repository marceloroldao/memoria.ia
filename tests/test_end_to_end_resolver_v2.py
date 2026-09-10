from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.end_to_end_resolver_v2 import EndToEndAddressResolver


def test_end_to_end_direct_frontier_from_text_only():
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma")
    resolver = EndToEndAddressResolver(memory)
    result = resolver.resolve_text("alpha beta")
    assert result.resolved is True
    assert result.ambiguous is False
    assert result.surface == "gamma"


def test_end_to_end_branching_remains_ambiguous():
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma")
    memory.ingest("alpha beta omega")
    resolver = EndToEndAddressResolver(memory)
    result = resolver.resolve_text("alpha beta")
    assert result.resolved is False
    assert result.ambiguous is True
    assert len(result.competing_addresses) == 2


def test_end_to_end_does_not_jump_across_shared_hub():
    memory = AddressTrajectoryMemory()
    memory.ingest("a hub x")
    memory.ingest("b hub y")
    resolver = EndToEndAddressResolver(memory)
    result = resolver.resolve_text("a hub")
    assert result.resolved is True
    assert result.surface == "x"


def test_end_to_end_multimodal_address_stream():
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("sensor:A", "sensor:B", "sensor:C"))
    resolver = EndToEndAddressResolver(memory)
    result = resolver.resolve_addresses(("sensor:A", "sensor:B"))
    assert result.resolved is True
    assert result.address == "sensor:C"


def test_end_to_end_restart_is_deterministic():
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma")
    before = EndToEndAddressResolver(memory).resolve_text("alpha beta")
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    after = EndToEndAddressResolver(restored).resolve_text("alpha beta")
    assert before == after


def test_end_to_end_query_is_read_only():
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma")
    before = memory.snapshot()
    EndToEndAddressResolver(memory).resolve_text("alpha beta")
    assert memory.snapshot() == before


def test_end_to_end_no_frontier_is_unresolved():
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta")
    result = EndToEndAddressResolver(memory).resolve_text("alpha beta")
    assert result.resolved is False
    assert result.ambiguous is False
    assert result.source == "no-contiguous-frontier"
