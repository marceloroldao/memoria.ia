from memoria_resolutiva.native_resolve import NativeResolveService
from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService
from memoria_resolutiva.product_identity import MemoryScope
from memoria_resolutiva.semantic_activation_resolver import SemanticActivationConversationResolver


def test_real_memory_ingest_to_native_answer_without_llm(tmp_path):
    evidence = ProductEvidenceService.open(tmp_path / "evidence", backend="sqlite", allow_fallback=False)
    conversation = ConversationSemanticService(evidence)
    conversation.ingest(
        role="user",
        text="camisa = preta",
        session_id="shirt-session",
        order=1,
    )
    resolver = SemanticActivationConversationResolver(conversation)
    native = NativeResolveService(resolver, min_confidence=0.75)
    scope = MemoryScope("org-a", application_id="web", agent_id="shirt-session")

    result = native.resolve(scope=scope, message="Qual era a camisa?")

    assert result.status == "RESOLVED"
    assert "camisa = preta" in result.text
    assert result.confidence >= 0.75
    assert result.external_calls == 0


def test_real_memory_unknown_intention_stays_unresolved_without_llm(tmp_path):
    evidence = ProductEvidenceService.open(tmp_path / "evidence", backend="sqlite", allow_fallback=False)
    conversation = ConversationSemanticService(evidence)
    conversation.ingest(role="user", text="camisa = preta", session_id="shirt-session", order=1)
    native = NativeResolveService(SemanticActivationConversationResolver(conversation))
    scope = MemoryScope("org-a", application_id="web", agent_id="shirt-session")

    result = native.resolve(scope=scope, message="qual é a senha do roteador?")

    assert result.status == "UNRESOLVED"
    assert result.text is None
    assert result.external_calls == 0
