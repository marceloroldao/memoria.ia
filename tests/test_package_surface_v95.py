from memoria_resolutiva import (
    ConsensusDecision,
    KnowledgeDescriptor,
    MemoryConfig,
    ResolutiveMemoryAPI,
)


def test_candidate_api_is_exported_from_package_root():
    assert ResolutiveMemoryAPI.API_VERSION == "0.95.0rc1"
    assert MemoryConfig().levels == 5
    assert MemoryConfig().max_strength == 1.25


def test_consensus_types_are_importable_from_package_root():
    a = KnowledgeDescriptor(
        "a", frozenset({"cup", "ceramic"}), frozenset({"vision"}), "same"
    )
    b = KnowledgeDescriptor(
        "b", frozenset({"cup", "ceramic"}), frozenset({"language"}), "same"
    )
    decision = ResolutiveMemoryAPI.compare(a, b)
    assert isinstance(decision, ConsensusDecision)
    assert decision.relation == "same"
