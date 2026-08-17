import pytest

from memoria_resolutiva.multitrajectory import MultiTrajectoryMemory


def test_multimodal_routes_share_one_payload():
    m = MultiTrajectoryMemory()
    m.store("cup", {"class": "cup"}, ("vision", "round", "handle"), modality="vision", provenance="robot-1")
    m.store("cup", {"class": "cup"}, ("language", "xicara"), modality="language", provenance="robot-1")
    m.store("cup", {"class": "cup"}, ("action", "grasp", "fragile"), modality="motor", provenance="robot-2")
    assert m.knowledge_count == 1
    assert m.route_count == 3
    assert m.resolve(("language", "xicara")).payload == {"class": "cup"}
    assert m.resolve(("vision", "round", "handle")).knowledge_id == "cup"
    assert m.duplication_ratio() == pytest.approx(2 / 3)


def test_individual_and_collective_provenance_coexist():
    m = MultiTrajectoryMemory()
    m.store("door-A", "sticks", ("private", "robot-7", "door-A"), modality="experience", provenance="robot-7")
    m.store("door-A", "sticks", ("collective", "building", "door-A"), modality="shared", provenance="fleet-consensus")
    node = m.resolve(("collective", "building", "door-A"))
    assert node.provenance == {"robot-7", "fleet-consensus"}
    assert m.knowledge_count == 1


def test_route_collision_is_rejected():
    m = MultiTrajectoryMemory()
    route = ("vision", "object")
    m.store("a", "A", route, modality="vision", provenance="r1")
    with pytest.raises(ValueError):
        m.store("b", "B", route, modality="vision", provenance="r2")


def test_same_id_cannot_silently_change_meaning():
    m = MultiTrajectoryMemory()
    m.store("bank", "financial", ("text", "money"), modality="text", provenance="r1")
    with pytest.raises(ValueError):
        m.store("bank", "database", ("text", "sql"), modality="text", provenance="r2")
