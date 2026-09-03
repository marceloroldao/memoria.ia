import pytest

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.factual_consolidation import FactualConsolidationService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex


def _fact(core: EvidenceCore, memory_id: str, subject: str, predicate: str, obj: str):
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
    MemoryProvenanceIndex(core).register(
        memory_id,
        source_type="user_assertion",
        namespace="s",
    )


def test_consolidation_requires_two_active_factual_supports():
    core = EvidenceCore()
    _fact(core, "u1", "Alt", "is_a", "cat")
    svc = FactualConsolidationService(core)

    with pytest.raises(ValueError, match="insufficient"):
        svc.consolidate(
            memory_id="abs1",
            subject="known-cats",
            predicate="includes",
            object="Alt",
            support_memory_ids=["u1"],
            namespace="s",
        )


def test_consolidation_rejects_generated_only_support():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    _fact(core, "u1", "Alt", "is_a", "cat")
    core.observe_relation(
        "Alt2", "is_a", "cat",
        evidence_id="a1", source_text="Alt2 is a cat",
        provenance="conversation", origin="assistant",
        confidence=1.0, namespace="s",
    )
    prov.register("a1", source_type="assistant_generated", namespace="s")

    svc = FactualConsolidationService(core)
    with pytest.raises(ValueError, match="not an active factual"):
        svc.consolidate(
            memory_id="abs1",
            subject="cats",
            predicate="share_type",
            object="cat",
            support_memory_ids=["u1", "a1"],
            namespace="s",
        )


def test_abstraction_keeps_all_supports_as_conjunctive_provenance():
    core = EvidenceCore()
    _fact(core, "u1", "Alt", "is_a", "cat")
    _fact(core, "u2", "Alt2", "is_a", "cat")
    svc = FactualConsolidationService(core)

    abstraction = svc.consolidate(
        memory_id="abs1",
        subject="Alt+Alt2",
        predicate="share_type",
        object="cat",
        support_memory_ids=["u1", "u2"],
        namespace="s",
    )

    meta = MemoryProvenanceIndex(core).inspect("abs1", namespace="s")
    assert abstraction.support_memory_ids == ("u1", "u2")
    assert meta.source_type == "derived_relation"
    assert meta.parent_memory_ids == ("u1", "u2")
    assert svc.is_factually_active("abs1", namespace="s") is True


def test_abstraction_becomes_nonfactual_when_required_support_is_corrected():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    _fact(core, "u1", "Alt", "is_a", "cat")
    _fact(core, "u2", "Alt2", "is_a", "cat")
    svc = FactualConsolidationService(core)
    svc.consolidate(
        memory_id="abs1",
        subject="Alt+Alt2",
        predicate="share_type",
        object="cat",
        support_memory_ids=["u1", "u2"],
        namespace="s",
    )

    _fact(core, "u2-v2", "Alt2", "is_a", "dog")
    prov.supersede("u2", by_memory_id="u2-v2", namespace="s")

    assert svc.is_factually_active("abs1", namespace="s") is False
    # Historical edge remains persisted for inspection/audit.
    assert any(edge.evidence_id == "abs1" for edge in core.active_edges(namespace="s"))
