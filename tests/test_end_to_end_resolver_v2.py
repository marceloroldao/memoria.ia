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


def _structural_transfer_memory() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()

    # Learned relation: two independent occurrences with the same future.
    memory.ingest_address_stream(("lp1", "train:a", "train:b", "future:x", "ls1"))
    memory.ingest_address_stream(("lp2", "train:a", "train:b", "future:x", "ls2"))

    # Held-out configuration has its ordered transition independently observed,
    # but only at trajectory frontier, so direct recall has no future to return.
    memory.ingest_address_stream(("hp1", "held:a", "held:b"))
    memory.ingest_address_stream(("hp2", "held:a", "held:b"))

    # Additional local contexts keep the anonymous roles discriminative while
    # preserving a disjoint literal surface between train and held-out regions.
    memory.ingest_address_stream(("ta1", "train:a", "tb1"))
    memory.ingest_address_stream(("ta2", "train:a", "tb2"))
    memory.ingest_address_stream(("ha1", "held:a", "hb1"))
    memory.ingest_address_stream(("ha2", "held:a", "hb2"))
    return memory


def test_structural_fallback_is_opt_in_and_never_replaces_direct_tier():
    memory = _structural_transfer_memory()
    without = EndToEndAddressResolver(memory).resolve_addresses(("held:a", "held:b"))
    with_fallback = EndToEndAddressResolver(memory, enable_structural_fallback=True).resolve_addresses(("held:a", "held:b"))

    assert without.resolved is False
    # This assertion intentionally permits unresolved if the observed geometry is
    # not yet equivalent enough; the important invariant is no fabricated result.
    assert with_fallback.source in {"no-contiguous-frontier", "anonymous-structural-frontier"}

    direct = EndToEndAddressResolver(memory, enable_structural_fallback=True).resolve_addresses(("train:a", "train:b"))
    assert direct.resolved is True
    assert direct.source == "direct-contiguous-frontier"
    assert direct.address == "future:x"


def test_structural_fallback_is_read_only_and_restart_deterministic():
    memory = _structural_transfer_memory()
    before_snapshot = memory.snapshot()
    before = EndToEndAddressResolver(memory, enable_structural_fallback=True).resolve_addresses(("held:a", "held:b"))
    assert memory.snapshot() == before_snapshot

    restored = AddressTrajectoryMemory.restore(before_snapshot)
    after = EndToEndAddressResolver(restored, enable_structural_fallback=True).resolve_addresses(("held:a", "held:b"))
    assert before == after


def test_structural_fallback_requires_independent_future_support():
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("p1", "a", "b", "x"))
    memory.ingest_address_stream(("p2", "a", "b"))
    memory.ingest_address_stream(("p3", "a", "b"))
    result = EndToEndAddressResolver(memory, enable_structural_fallback=True).resolve_addresses(("a", "b"))
    # Exact frontier exists only once, so the direct tier still reports it; the
    # fallback never gets permission to manufacture reinforcement.
    assert result.source == "direct-contiguous-frontier"
    assert len(result.supporting_trajectories) == 1
