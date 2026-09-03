from pathlib import Path

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex, ProvenanceCandidate
from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService


def _service(root: Path) -> ConversationSemanticService:
    return ConversationSemanticService(ProductEvidenceService.open(root, backend="sqlite", allow_fallback=True))


def test_generated_root_is_persisted_but_not_active_factual_authority():
    core = EvidenceCore()
    index = MemoryProvenanceIndex(core)
    index.register("generated", source_type="assistant_generated", created_order=1, namespace="s")

    assert index.inspect("generated", namespace="s").source_type == "assistant_generated"
    assert index.active_ultimate_source("generated", namespace="s") is None
    assert index.ultimate_source("generated", namespace="s").source_type == "assistant_generated"
    assert index.select([ProvenanceCandidate("generated", 1.0, 1)], namespace="s") is None


def test_assistant_echo_with_user_root_stays_in_user_factual_lineage():
    core = EvidenceCore()
    index = MemoryProvenanceIndex(core)
    index.register("user-fact", source_type="user_assertion", created_order=1, namespace="s")
    index.register(
        "assistant-echo",
        source_type="assistant_generated",
        parent_memory_ids=("user-fact",),
        created_order=2,
        namespace="s",
    )

    root = index.active_ultimate_source("assistant-echo", namespace="s")
    assert root is not None
    assert root.memory_id == "user-fact"
    assert root.source_type == "user_assertion"


def test_assistant_invention_cannot_become_fact_or_create_false_conflict(tmp_path: Path):
    root = tmp_path / "evidence"
    service = _service(root)

    service.ingest(role="assistant", text="meu carro é Renegade", session_id="chat", order=1)
    generated_only = service.resolve(query="qual carro?", session_id="chat")
    assert generated_only.status == "UNRESOLVED"

    service.ingest(role="user", text="meu carro é Jeep", session_id="chat", order=2)
    factual = service.resolve(query="qual carro?", session_id="chat")
    assert factual.status == "HIT"
    assert "Jeep" in factual.selected_context
    assert "Renegade" not in factual.selected_context
    assert factual.provenance
    assert factual.provenance[0]["source_type"] == "user_assertion"

    restarted = _service(root)
    again = restarted.resolve(query="qual carro?", session_id="chat")
    assert again.status == "HIT"
    assert "Jeep" in again.selected_context
    assert "Renegade" not in again.selected_context
