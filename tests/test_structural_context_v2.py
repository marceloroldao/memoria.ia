import pytest

from memoria_resolutiva.structural_context_v2 import StructuralContextAddressV2


def test_context_address_v2_keeps_stable_identity_while_payload_evolves():
    context = StructuralContextAddressV2()

    first = context.revise(
        900,
        hierarchy_id="ctx",
        sequence=1,
        payload_addresses=[10, 20],
        trajectory_ids=["t:1"],
        provenance_ids=["p:1"],
    )
    second = context.revise(
        900,
        hierarchy_id="ctx",
        sequence=2,
        payload_addresses=[20, 30],
        trajectory_ids=["t:2"],
        provenance_ids=["p:2"],
    )

    assert first.address == second.address == 900
    assert first.payload_addresses == (10, 20)
    assert second.payload_addresses == (20, 30)
    assert second.predecessor_revision_id == first.revision_id
    assert context.current(900, hierarchy_id="ctx") == second
    assert context.history(900, hierarchy_id="ctx") == (first, second)


def test_context_address_v2_keeps_parallel_contexts_isolated():
    context = StructuralContextAddressV2()
    context.revise(900, hierarchy_id="ctx", sequence=1, payload_addresses=[1, 2])
    context.revise(901, hierarchy_id="ctx", sequence=1, payload_addresses=[7, 8])

    assert context.current(900, hierarchy_id="ctx").payload_addresses == (1, 2)
    assert context.current(901, hierarchy_id="ctx").payload_addresses == (7, 8)


def test_context_address_v2_reuses_generic_revision_invariants():
    context = StructuralContextAddressV2()
    first = context.revise(900, hierarchy_id="ctx", sequence=1, payload_addresses=[1, 2])
    repeated = context.revise(900, hierarchy_id="ctx", sequence=1, payload_addresses=[1, 2])

    assert repeated == first
    assert len(context.history(900, hierarchy_id="ctx")) == 1

    with pytest.raises(ValueError, match="same address sequence"):
        context.revise(900, hierarchy_id="ctx", sequence=1, payload_addresses=[1, 3])
