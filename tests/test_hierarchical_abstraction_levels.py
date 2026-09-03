import pytest

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.factual_consolidation import FactualConsolidationService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex


def _fact(core: EvidenceCore, prov: MemoryProvenanceIndex, memory_id: str, subject: str):
    core.observe_relation(
        subject, "is_a", "cat",
        evidence_id=memory_id,
        source_text=f"{subject} is a cat",
        origin="user",
        confidence=1.0,
        namespace="s",
    )
    prov.register(memory_id, source_type="user_assertion", namespace="s")


def test_root_facts_are_level_zero_and_first_abstraction_is_level_one():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    svc = FactualConsolidationService(core)
    _fact(core, prov, "u1", "Alt")
    _fact(core, prov, "u2", "Alt2")

    assert svc.abstraction_level("u1", namespace="s") == 0
    abstraction = svc.consolidate(
        memory_id="a1",
        subject="pattern:cats",
        predicate="supported_by",
        object="cat-members",
        support_memory_ids=("u1", "u2"),
        namespace="s",
    )
    assert abstraction.level == 1
    assert svc.abstraction_level("a1", namespace="s") == 1


def test_abstraction_over_abstractions_advances_one_level():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    svc = FactualConsolidationService(core)
    for memory_id, subject in (("u1", "Alt"), ("u2", "Alt2"), ("u3", "Mia"), ("u4", "Nina")):
        _fact(core, prov, memory_id, subject)

    a1 = svc.consolidate(memory_id="a1", subject="cats:a", predicate="kind", object="cat-group", support_memory_ids=("u1", "u2"), namespace="s")
    a2 = svc.consolidate(memory_id="a2", subject="cats:b", predicate="kind", object="cat-group", support_memory_ids=("u3", "u4"), namespace="s")
    top = svc.consolidate(memory_id="a3", subject="cats", predicate="abstracts", object="cat-groups", support_memory_ids=("a1", "a2"), namespace="s")

    assert (a1.level, a2.level, top.level) == (1, 1, 2)
    assert prov.inspect("a3", namespace="s").parent_memory_ids == ("a1", "a2")


def test_mixed_support_uses_deepest_parent_level():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    svc = FactualConsolidationService(core)
    for memory_id, subject in (("u1", "Alt"), ("u2", "Alt2"), ("u3", "Mia")):
        _fact(core, prov, memory_id, subject)

    a1 = svc.consolidate(memory_id="a1", subject="cats:a", predicate="kind", object="cat-group", support_memory_ids=("u1", "u2"), namespace="s")
    mixed = svc.consolidate(memory_id="a2", subject="mixed", predicate="kind", object="higher", support_memory_ids=(a1.memory_id, "u3"), namespace="s")
    assert mixed.level == 2


def test_max_level_blocks_unbounded_recursive_abstraction():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    svc = FactualConsolidationService(core)
    for memory_id, subject in (("u1", "Alt"), ("u2", "Alt2"), ("u3", "Mia"), ("u4", "Nina")):
        _fact(core, prov, memory_id, subject)

    svc.consolidate(memory_id="a1", subject="cats:a", predicate="kind", object="cat-group", support_memory_ids=("u1", "u2"), namespace="s", max_level=2)
    svc.consolidate(memory_id="a2", subject="cats:b", predicate="kind", object="cat-group", support_memory_ids=("u3", "u4"), namespace="s", max_level=2)
    svc.consolidate(memory_id="a3", subject="cats", predicate="abstracts", object="cat-groups", support_memory_ids=("a1", "a2"), namespace="s", max_level=2)

    with pytest.raises(ValueError, match="exceeds max_level"):
        svc.consolidate(memory_id="a4", subject="meta", predicate="abstracts", object="cats", support_memory_ids=("a3", "a2"), namespace="s", max_level=2)
