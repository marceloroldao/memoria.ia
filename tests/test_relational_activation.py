from types import SimpleNamespace

from memoria_resolutiva.llm_adapter import LLMResponse, LLMUsage
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_evidence import ProductEvidenceService
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.relational_activation import activate


class CaptureAdapter:
    provider_name = "capture"
    model_name = "capture-v1"

    def __init__(self):
        self.calls = []

    def generate(self, *, message: str, context):
        self.calls.append((message, tuple(context)))
        return LLMResponse(
            text="captured",
            provider=self.provider_name,
            model=self.model_name,
            usage=LLMUsage(input_tokens=1, output_tokens=1, estimated_cost_usd=0.0),
        )


class StructuralResolver:
    def __init__(self, evidence):
        self.evidence = evidence
        self.resolve_calls = []

    def resolve(self, *, query: str, session_id: str | None = None):
        self.resolve_calls.append((query, session_id))
        return SimpleNamespace(
            status="UNRESOLVED",
            confidence=0.0,
            selected_context="",
            relations=(),
            provenance=(),
            memory_ids=(),
        )


def _observe(core, subject, predicate, object_, evidence_id, namespace, confidence=0.95):
    core.observe_relation(
        subject,
        predicate,
        object_,
        evidence_id=evidence_id,
        source_text=f"{subject} {predicate} {object_}",
        provenance="test",
        origin="test",
        confidence=confidence,
        namespace=namespace,
    )


def test_structural_activation_walks_two_hops_without_language_queries(tmp_path):
    evidence = ProductEvidenceService.open(tmp_path / "evidence", backend="sqlite", allow_fallback=True)
    namespace = "offia:internet"
    _observe(evidence.core, "internet", "depends_on", "PPPoE", "e1", namespace, 0.95)
    _observe(evidence.core, "PPPoE", "upstream", "OLT", "e2", namespace, 0.90)
    _observe(evidence.core, "OLT", "located_at", "POP", "e3", namespace, 0.99)

    result = activate(
        SimpleNamespace(evidence=evidence),
        concept="internet",
        session_id=namespace,
        depth=2,
        budget=1200,
        hop_decay=0.72,
        min_confidence=0.45,
    )

    assert result.status == "HIT"
    assert "internet | depends_on | PPPoE" in result.selected_context
    assert "PPPoE | upstream | OLT" in result.selected_context
    assert "OLT | located_at | POP" not in result.selected_context
    assert result.memory_ids == ("e1", "e2")


def test_structural_activation_applies_confidence_decay(tmp_path):
    evidence = ProductEvidenceService.open(tmp_path / "evidence", backend="sqlite", allow_fallback=True)
    namespace = "offia:confidence"
    _observe(evidence.core, "internet", "depends_on", "PPPoE", "e1", namespace, 0.95)
    _observe(evidence.core, "PPPoE", "upstream", "OLT", "e2", namespace, 0.50)

    result = activate(
        SimpleNamespace(evidence=evidence),
        concept="internet",
        session_id=namespace,
        depth=2,
        budget=1200,
        hop_decay=0.72,
        min_confidence=0.45,
    )

    assert result.status == "HIT"
    assert "internet | depends_on | PPPoE" in result.selected_context
    assert "PPPoE | upstream | OLT" not in result.selected_context


def test_structural_activation_respects_context_budget(tmp_path):
    evidence = ProductEvidenceService.open(tmp_path / "evidence", backend="sqlite", allow_fallback=True)
    namespace = "offia:budget"
    _observe(evidence.core, "internet", "depends_on", "PPPoE", "e1", namespace, 0.95)
    _observe(evidence.core, "internet", "backup_path", "satellite-backhaul-with-long-name", "e2", namespace, 0.95)

    result = activate(
        SimpleNamespace(evidence=evidence),
        concept="internet",
        session_id=namespace,
        depth=1,
        budget=len("internet | depends_on | PPPoE"),
        hop_decay=0.72,
        min_confidence=0.45,
    )

    assert result.selected_context == "internet | depends_on | PPPoE"


def test_chat_prefers_structural_activation_and_does_not_emit_textual_probe(tmp_path):
    evidence = ProductEvidenceService.open(tmp_path / "evidence", backend="sqlite", allow_fallback=True)
    namespace = "offia:chat-structural"
    _observe(evidence.core, "internet", "depends_on", "PPPoE", "e1", namespace, 0.95)
    _observe(evidence.core, "PPPoE", "upstream", "OLT", "e2", namespace, 0.90)

    resolver = StructuralResolver(evidence)
    adapter = CaptureAdapter()
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    chat = ProductChatService(memory, adapter, conversation_resolver=resolver)
    scope = MemoryScope(
        "org-a",
        application_id="offia",
        user_id="user-1",
        agent_id=namespace,
    )

    result = chat.run(scope=scope, message="A internet caiu", mode="memoria")

    # Only the original user input goes through the conversational resolver.
    # Structural activation then walks evidence edges directly.
    assert resolver.resolve_calls == [("A internet caiu", namespace)]
    assert result.metrics.memory_hits == 1
    assert "internet | depends_on | PPPoE" in result.context[0]
    assert "PPPoE | upstream | OLT" in result.context[0]
    assert adapter.calls == [("A internet caiu", result.context)]
