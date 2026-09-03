from __future__ import annotations

from memoria_resolutiva.conversation_semantic_bridge import AutoSemanticConsolidationConversationService
from memoria_resolutiva.product_evidence import ProductEvidenceService
from memoria_resolutiva.reference_conversation import ConversationSemanticService


def _consolidated_rows(evidence: ProductEvidenceService, *, namespace: str | None = None):
    return [
        edge for edge in evidence.core.evidence_history(namespace=namespace)
        if edge.origin == "factual-consolidation"
    ]


def test_repeated_user_fact_is_automatically_consolidated_and_persisted(tmp_path):
    evidence = ProductEvidenceService.open(tmp_path / "evidence")
    backend = ConversationSemanticService(evidence)
    service = AutoSemanticConsolidationConversationService(backend, evidence)

    first = service.ingest(
        role="user",
        text="bateria é carregada",
        session_id="s1",
        order=1,
        timestamp="2026-09-03T10:00:00Z",
    )
    assert first.relations
    assert _consolidated_rows(evidence, namespace="s1") == []

    second = service.ingest(
        role="user",
        text="bateria é carregada",
        session_id="s1",
        order=2,
        timestamp="2026-09-03T10:01:00Z",
    )
    assert second.relations
    rows = _consolidated_rows(evidence, namespace="s1")
    assert len(rows) == 1
    assert rows[0].subject.casefold() == "bateria"
    assert rows[0].object.casefold() == "carregada"
    assert evidence.receipt is not None

    # A third independent confirmation strengthens history but does not create a
    # duplicate semantic-memory identity for the same normalized claim.
    service.ingest(
        role="user",
        text="bateria é carregada",
        session_id="s1",
        order=3,
        timestamp="2026-09-03T10:02:00Z",
    )
    assert len(_consolidated_rows(evidence, namespace="s1")) == 1


def test_assistant_repetition_cannot_trigger_automatic_factual_consolidation(tmp_path):
    evidence = ProductEvidenceService.open(tmp_path / "evidence")
    backend = ConversationSemanticService(evidence)
    service = AutoSemanticConsolidationConversationService(backend, evidence)

    service.ingest(
        role="user",
        text="bateria é carregada",
        session_id="s1",
        order=1,
        timestamp="2026-09-03T10:00:00Z",
    )
    service.ingest(
        role="assistant",
        text="bateria é carregada",
        session_id="s1",
        order=2,
        timestamp="2026-09-03T10:01:00Z",
    )
    service.ingest(
        role="assistant",
        text="bateria é carregada",
        session_id="s1",
        order=3,
        timestamp="2026-09-03T10:02:00Z",
    )

    assert _consolidated_rows(evidence, namespace="s1") == []
