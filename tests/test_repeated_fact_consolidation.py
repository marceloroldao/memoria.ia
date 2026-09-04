from __future__ import annotations

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex
from memoria_resolutiva.repeated_fact_consolidation import RepeatedFactConsolidator


def _root(
    core: EvidenceCore,
    provenance: MemoryProvenanceIndex,
    *,
    memory_id: str,
    source_type: str = "user_assertion",
    namespace: str | None = None,
    order: int = 1,
) -> None:
    core.observe_relation(
        f"turn:{memory_id}",
        "conversation_text",
        memory_id,
        evidence_id=memory_id,
        source_text=memory_id,
        provenance="test",
        origin="conversation-user" if source_type != "assistant_generated" else "conversation-assistant",
        confidence=1.0,
        namespace=namespace,
    )
    provenance.register(
        memory_id,
        source_type=source_type,
        created_order=order,
        namespace=namespace,
    )


def _relation(
    core: EvidenceCore,
    provenance: MemoryProvenanceIndex,
    *,
    memory_id: str,
    parent_id: str,
    subject: str = "bateria",
    predicate: str = "is",
    object: str = "carregada",
    namespace: str | None = None,
    confidence: float = 0.95,
) -> None:
    core.observe_relation(
        subject,
        predicate,
        object,
        evidence_id=memory_id,
        source_text=f"{subject} {predicate} {object}",
        provenance="test",
        origin="conversation-user",
        confidence=confidence,
        namespace=namespace,
    )
    provenance.register(
        memory_id,
        source_type="derived_relation",
        parent_memory_ids=(parent_id,),
        namespace=namespace,
    )


def test_two_independent_factual_roots_form_one_semantic_abstraction():
    core = EvidenceCore()
    provenance = MemoryProvenanceIndex(core)
    _root(core, provenance, memory_id="u1", order=1)
    _root(core, provenance, memory_id="u2", order=2)
    _relation(core, provenance, memory_id="r1", parent_id="u1")
    _relation(core, provenance, memory_id="r2", parent_id="u2")

    consolidator = RepeatedFactConsolidator(core)
    candidates = consolidator.candidates()
    assert len(candidates) == 1
    assert candidates[0].factual_root_ids == ("u1", "u2")
    assert candidates[0].support_memory_ids == ("r1", "r2")

    created = consolidator.consolidate_all()
    assert len(created) == 1
    abstraction = created[0]
    assert abstraction.level == 1
    assert abstraction.subject == "bateria"
    assert abstraction.object == "carregada"
    assert abstraction.support_memory_ids == ("r1", "r2")
    assert consolidator.consolidation.is_factually_active(abstraction.memory_id)

    # Idempotent: scanning again does not create a second semantic memory.
    assert consolidator.consolidate_all() == ()


def test_low_confidence_repetition_does_not_promote_to_semantic_fact():
    core = EvidenceCore()
    provenance = MemoryProvenanceIndex(core)
    _root(core, provenance, memory_id="u1", order=1)
    _root(core, provenance, memory_id="u2", order=2)
    _relation(core, provenance, memory_id="r1", parent_id="u1", confidence=0.85)
    _relation(core, provenance, memory_id="r2", parent_id="u2", confidence=0.85)

    consolidator = RepeatedFactConsolidator(core)
    assert consolidator.candidates() == ()
    assert consolidator.consolidate_all() == ()


def test_weak_second_support_cannot_confirm_strong_claim():
    core = EvidenceCore()
    provenance = MemoryProvenanceIndex(core)
    _root(core, provenance, memory_id="u1", order=1)
    _root(core, provenance, memory_id="u2", order=2)
    _relation(core, provenance, memory_id="r1", parent_id="u1", confidence=0.95)
    _relation(core, provenance, memory_id="r2", parent_id="u2", confidence=0.85)

    assert RepeatedFactConsolidator(core).candidates() == ()


def test_two_relations_from_same_factual_root_count_once():
    core = EvidenceCore()
    provenance = MemoryProvenanceIndex(core)
    _root(core, provenance, memory_id="u1")
    _relation(core, provenance, memory_id="r1", parent_id="u1")
    _relation(core, provenance, memory_id="r2", parent_id="u1")

    consolidator = RepeatedFactConsolidator(core)
    assert consolidator.candidates() == ()
    assert consolidator.consolidate_all() == ()


def test_assistant_generated_repetition_never_counts_as_factual_support():
    core = EvidenceCore()
    provenance = MemoryProvenanceIndex(core)
    _root(core, provenance, memory_id="a1", source_type="assistant_generated", order=1)
    _root(core, provenance, memory_id="a2", source_type="assistant_generated", order=2)
    _relation(core, provenance, memory_id="r1", parent_id="a1")
    _relation(core, provenance, memory_id="r2", parent_id="a2")

    consolidator = RepeatedFactConsolidator(core)
    assert consolidator.candidates() == ()
    assert consolidator.consolidate_all() == ()


def test_mixed_user_and_assistant_support_is_still_insufficient():
    core = EvidenceCore()
    provenance = MemoryProvenanceIndex(core)
    _root(core, provenance, memory_id="u1", source_type="user_assertion", order=1)
    _root(core, provenance, memory_id="a1", source_type="assistant_generated", order=2)
    _relation(core, provenance, memory_id="r1", parent_id="u1")
    _relation(core, provenance, memory_id="r2", parent_id="a1")

    assert RepeatedFactConsolidator(core).candidates() == ()


def test_normalization_groups_case_and_accent_equivalent_claims():
    core = EvidenceCore()
    provenance = MemoryProvenanceIndex(core)
    _root(core, provenance, memory_id="u1", order=1)
    _root(core, provenance, memory_id="u2", order=2)
    _relation(
        core,
        provenance,
        memory_id="r1",
        parent_id="u1",
        subject="BATERIA",
        object="CARREGÁDA",
    )
    _relation(
        core,
        provenance,
        memory_id="r2",
        parent_id="u2",
        subject="bateria",
        object="carregada",
    )

    candidates = RepeatedFactConsolidator(core).candidates()
    assert len(candidates) == 1
    assert candidates[0].factual_root_ids == ("u1", "u2")


def test_namespace_isolation_prevents_cross_session_confirmation():
    core = EvidenceCore()
    provenance = MemoryProvenanceIndex(core)
    _root(core, provenance, memory_id="u1", namespace="one")
    _root(core, provenance, memory_id="u2", namespace="two")
    _relation(core, provenance, memory_id="r1", parent_id="u1", namespace="one")
    _relation(core, provenance, memory_id="r2", parent_id="u2", namespace="two")

    consolidator = RepeatedFactConsolidator(core)
    assert consolidator.candidates(namespace="one") == ()
    assert consolidator.candidates(namespace="two") == ()


def test_superseding_one_root_invalidates_consolidated_memory():
    core = EvidenceCore()
    provenance = MemoryProvenanceIndex(core)
    _root(core, provenance, memory_id="u1", order=1)
    _root(core, provenance, memory_id="u2", order=2)
    _relation(core, provenance, memory_id="r1", parent_id="u1")
    _relation(core, provenance, memory_id="r2", parent_id="u2")

    consolidator = RepeatedFactConsolidator(core)
    abstraction = consolidator.consolidate_all()[0]
    assert consolidator.consolidation.is_factually_active(abstraction.memory_id)

    _root(core, provenance, memory_id="correction", source_type="user_correction", order=3)
    provenance.supersede("u2", by_memory_id="correction")
    assert not consolidator.consolidation.is_factually_active(abstraction.memory_id)
