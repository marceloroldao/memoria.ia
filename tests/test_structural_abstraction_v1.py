from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.factual_consolidation import FactualConsolidationService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex
from memoria_resolutiva.structural_abstraction import StructuralAbstractionDetector


def _fact(core: EvidenceCore, prov: MemoryProvenanceIndex, subject: str, predicate: str, obj: str, memory_id: str):
    core.observe_relation(
        subject,
        predicate,
        obj,
        evidence_id=memory_id,
        source_text=f"{subject} {predicate} {obj}",
        provenance="conversation",
        origin="user",
        confidence=1.0,
        namespace="s",
    )
    prov.register(memory_id, source_type="user_assertion", namespace="s")


def test_detects_repeated_factual_predicate_object_pattern():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    _fact(core, prov, "Alt", "is_a", "cat", "u1")
    _fact(core, prov, "Alt2", "is_a", "cat", "u2")

    candidates = StructuralAbstractionDetector(core).discover(namespace="s")
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.predicate == "is_a"
    assert candidate.object == "cat"
    assert candidate.subjects == ("Alt", "Alt2")
    assert candidate.support_memory_ids == ("u1", "u2")


def test_generated_only_pattern_is_not_a_candidate():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    for subject, memory_id in (("A", "a1"), ("B", "a2")):
        core.observe_relation(
            subject,
            "is_a",
            "cat",
            evidence_id=memory_id,
            source_text=f"{subject} is_a cat",
            provenance="assistant",
            origin="assistant",
            confidence=1.0,
            namespace="s",
        )
        prov.register(memory_id, source_type="assistant_generated", namespace="s")

    assert StructuralAbstractionDetector(core).discover(namespace="s") == ()


def test_distinct_subjects_are_required():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    _fact(core, prov, "Alt", "is_a", "cat", "u1")
    core.observe_relation(
        "Alt",
        "is_a",
        "cat",
        evidence_id="u2",
        source_text="Alt is_a cat again",
        provenance="conversation",
        origin="user2",
        confidence=1.0,
        namespace="s",
    )
    prov.register("u2", source_type="user_assertion", namespace="s")

    assert StructuralAbstractionDetector(core).discover(namespace="s") == ()


def test_candidate_can_be_promoted_through_factual_consolidation():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    _fact(core, prov, "Alt", "is_a", "cat", "u1")
    _fact(core, prov, "Alt2", "is_a", "cat", "u2")

    candidate = StructuralAbstractionDetector(core).discover(namespace="s")[0]
    abstraction = FactualConsolidationService(core).consolidate(
        memory_id="abs:cats",
        subject="group:Alt,Alt2",
        predicate="shares_relation",
        object=f"{candidate.predicate}:{candidate.object}",
        support_memory_ids=candidate.support_memory_ids,
        namespace="s",
    )
    assert abstraction.support_memory_ids == ("u1", "u2")
    assert FactualConsolidationService(core).is_factually_active("abs:cats", namespace="s") is True
