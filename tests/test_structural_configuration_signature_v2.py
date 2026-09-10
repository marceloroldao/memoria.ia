from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.structural_configuration_signature_v2 import configuration_role_signature


def _memory_for_role_transfer():
    memory = AddressTrajectoryMemory()

    # Two disjoint literal regions with the same anonymous forward geometry.
    # Each transition is independently supported; no reverse edge is added here,
    # so direction is observable from topology rather than literal identity.
    for i in (1, 2):
        memory.ingest_address_stream((f"tf{i}", "train:a", "train:b", f"tfs{i}"))
        memory.ingest_address_stream((f"hf{i}", "held:a", "held:b", f"hfs{i}"))
    return memory


def test_disjoint_literal_addresses_can_share_configuration_signature_by_role():
    memory = _memory_for_role_transfer()
    learned = configuration_role_signature(memory, ("train:a", "train:b"))
    held = configuration_role_signature(memory, ("held:a", "held:b"))
    assert learned.supported is True
    assert held.supported is True
    assert learned.signature_id == held.signature_id


def test_reverse_order_fails_closed_when_topology_supports_only_forward_transition():
    memory = _memory_for_role_transfer()
    forward = configuration_role_signature(memory, ("train:a", "train:b"))
    reverse = configuration_role_signature(memory, ("train:b", "train:a"))
    assert forward.supported is True
    assert reverse.supported is False
    assert reverse.signature_id is None
    assert reverse.reason == "insufficient-transition-support"


def test_perfectly_symmetric_bidirectional_topology_does_not_invent_orientation():
    memory = AddressTrajectoryMemory()
    for i in (1, 2):
        memory.ingest_address_stream((f"f{i}", "sym:a", "sym:b", f"fs{i}"))
        memory.ingest_address_stream((f"r{i}", "sym:b", "sym:a", f"rs{i}"))

    forward = configuration_role_signature(memory, ("sym:a", "sym:b"))
    reverse = configuration_role_signature(memory, ("sym:b", "sym:a"))
    assert forward.supported is True
    assert reverse.supported is True
    # With identical anonymous roles and equally supported directions there is no
    # structural information that distinguishes orientation. Equality is correct;
    # forcing a difference would re-introduce hidden identity/semantic knowledge.
    assert forward.signature_id == reverse.signature_id


def test_unseen_address_fails_closed():
    memory = _memory_for_role_transfer()
    result = configuration_role_signature(memory, ("never-seen",))
    assert result.supported is False
    assert result.signature_id is None
    assert result.reason == "unseen-address"


def test_single_occurrence_cannot_define_transferable_role():
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("p", "once", "q"))
    result = configuration_role_signature(memory, ("once",))
    assert result.supported is False
    assert result.reason == "insufficient-independent-support"
