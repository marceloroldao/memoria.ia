from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.end_to_end_structural_resolver_v2 import EndToEndStructuralResolver


def test_direct_evidence_still_has_absolute_precedence():
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("a", "b", "c"), surfaces=("a", "b", "c"))
    resolver = EndToEndStructuralResolver(memory)
    result = resolver.resolve_addresses(("a", "b"))
    assert result.resolution.resolved is True
    assert result.resolution.address == "c"
    assert result.resolution.source == "direct-contiguous-frontier"
    assert result.diagnostics.witnesses == 0


def test_unseen_literal_configuration_does_not_gain_false_equivalence():
    memory = AddressTrajectoryMemory()
    # Two independently repeated origins converge through the same bridge/terminal.
    memory.ingest_address_stream(("left", "p", "q", "x"))
    memory.ingest_address_stream(("right", "p", "q", "x"))
    memory.ingest_address_stream(("left", "p", "q", "x"))
    memory.ingest_address_stream(("right", "p", "q", "x"))

    resolver = EndToEndStructuralResolver(memory)
    result = resolver.resolve_addresses(("unseen",))
    assert result.resolution.resolved is False
    assert result.resolution.ambiguous is False
    assert result.resolution.source == "unresolved-after-structural-fallback"
    assert result.diagnostics.witnesses >= 2


def test_snapshot_is_not_modified_by_fallback_attempt():
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("left", "p", "q", "x"))
    memory.ingest_address_stream(("right", "p", "q", "x"))
    memory.ingest_address_stream(("left", "p", "q", "x"))
    memory.ingest_address_stream(("right", "p", "q", "x"))
    before = memory.snapshot()
    EndToEndStructuralResolver(memory).resolve_addresses(("unseen",))
    assert memory.snapshot() == before
