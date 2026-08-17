from pathlib import Path

from memoria_resolutiva.api_v90 import ResolutiveMemoryAPI
from memoria_resolutiva.distributed_consensus import KnowledgeDescriptor


def test_release_gate_end_to_end(tmp_path: Path):
    m = ResolutiveMemoryAPI()
    private = ("private", "robot-1", "vision", "cup")
    collective = ("collective", "fleet", "language", "cup")
    payload = {"class": "cup", "fragile": True}

    m.remember("cup", payload, private, modality="vision", provenance="robot-1")
    m.remember("cup", payload, collective, modality="language", provenance="fleet")

    for _ in range(32):
        m.reinforce(private)
        m.reinforce(collective)
    for _ in range(24):
        m.challenge(private)

    assert m.recall(private) is None
    assert m.recall(private, include_inactive=True).knowledge_id == "cup"
    assert m.recall(collective).knowledge_id == "cup"
    assert m.route_status(private).historical_depth == 4

    path = tmp_path / "memory.snapshot"
    m.save(path)
    restored = ResolutiveMemoryAPI.load(path)

    assert restored.recall(private) is None
    assert restored.recall(private, include_inactive=True).knowledge_id == "cup"
    assert restored.recall(collective).knowledge_id == "cup"
    assert restored.route_status(private).historical_depth == 4

    a = KnowledgeDescriptor("a", frozenset({"cup", "ceramic", "handle"}), frozenset({"vision"}), "fp-a")
    b = KnowledgeDescriptor("b", frozenset({"cup", "ceramic", "handle", "drink", "object"}), frozenset({"language"}), "fp-b")
    assert restored.compare(a, b).relation == "related"
