from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.structural_configuration_signature_v2 import configuration_role_signature


def _memory_for_role_transfer():
    memory = AddressTrajectoryMemory()
    # train:a and held:a occupy the same anonymous role in disjoint local regions.
    for prefix in ("t1", "t2"):
        memory.ingest_address_stream((prefix, "train:a", "m1", "z1"))
    for prefix in ("h1", "h2"):
        memory.ingest_address_stream((prefix, "held:a", "m2", "z2"))

    for prefix in ("t3", "t4"):
        memory.ingest_address_stream((prefix, "train:b", "n1", "w1"))
    for prefix in ("h3", "h4"):
        memory.ingest_address_stream((prefix, "held:b", "n2", "w2"))
    return memory


def test_disjoint_literal_addresses_can_share_configuration_signature_by_role():
    memory = _memory_for_role_transfer()
    learned = configuration_role_signature(memory, ("train:a", "train:b"))
    held = configuration_role_signature(memory, ("held:a", "held:b"))
    assert learned.supported is True
    assert held.supported is True
    assert learned.signature_id == held.signature_id


def test_order_is_part_of_structural_configuration_signature():
    memory = _memory_for_role_transfer()
    forward = configuration_role_signature(memory, ("train:a", "train:b"))
    reverse = configuration_role_signature(memory, ("train:b", "train:a"))
    assert forward.supported is True
    assert reverse.supported is True
    assert forward.signature_id != reverse.signature_id


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
