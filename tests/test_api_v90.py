from memoria_resolutiva.api_v90 import MemoryConfig, ResolutiveMemoryAPI
from memoria_resolutiva.distributed_consensus import KnowledgeDescriptor


def test_public_api_multimodal_shared_payload_and_route_isolation():
    m = ResolutiveMemoryAPI(MemoryConfig(levels=5, max_strength=1.25))
    visual = ("private", "robot-7", "vision", "cup")
    collective = ("collective", "fleet", "language", "cup")
    payload = {"class": "cup", "fragile": True}
    m.remember("cup", payload, visual, modality="vision", provenance="robot-7")
    m.remember("cup", payload, collective, modality="language", provenance="fleet")
    for _ in range(32):
        m.reinforce(visual)
        m.reinforce(collective)
    assert m.recall(visual).knowledge_id == "cup"
    assert m.recall(collective).knowledge_id == "cup"
    for _ in range(24):
        m.challenge(visual)
    assert m.recall(visual) is None
    assert m.recall(visual, include_inactive=True).knowledge_id == "cup"
    assert m.recall(collective).knowledge_id == "cup"
    assert m.route_status(visual).historical_depth == 4


def test_public_api_consensus_is_non_destructive():
    a = KnowledgeDescriptor("a", frozenset({"cup", "ceramic", "handle"}), frozenset({"vision"}), "fp-a")
    b = KnowledgeDescriptor("b", frozenset({"cup", "ceramic", "handle", "drink", "object"}), frozenset({"language"}), "fp-b")
    decision = ResolutiveMemoryAPI.compare(a, b)
    assert decision.relation == "related"
    assert decision.relation != "same"


def test_default_config_is_frozen_candidate():
    c = MemoryConfig()
    assert c.levels == 5
    assert c.max_strength == 1.25
    assert ResolutiveMemoryAPI.API_VERSION == "0.95.0rc1"
