from __future__ import annotations

import pytest

from memoria_resolutiva.conversation_contract import ConversationIngestResult, ConversationResolveResult
from memoria_resolutiva.evidence_temporal_bridge import EpistemicSource
from memoria_resolutiva.response_validator import ResponseClaim, ResponseClaimStatus
from memoria_resolutiva.topological_conversation_runtime import TopologicalConversationRuntime
from memoria_resolutiva.topological_memory import TemporalOperator


class FakeConversationService:
    def __init__(self) -> None:
        self.flush_calls = 0
        self.ingest_calls: list[dict] = []
        self.next_relations: tuple[dict, ...] = ()
        self.next_memory_ids: tuple[str, ...] = ("turn-1",)

    def ingest(
        self,
        *,
        role: str,
        text: str,
        session_id: str | None = None,
        order: int | None = None,
        timestamp: str | None = None,
        parent_memory_ids=(),
        corrects_memory_ids=(),
    ) -> ConversationIngestResult:
        self.ingest_calls.append({
            "role": role,
            "text": text,
            "session_id": session_id,
            "order": order,
            "timestamp": timestamp,
        })
        return ConversationIngestResult(
            self.next_memory_ids,
            self.next_relations,
            not self.next_relations,
        )

    def resolve(self, *, query: str, session_id: str | None = None) -> ConversationResolveResult:
        raise AssertionError("topological runtime must not delegate cognitive resolve to legacy resolve")

    def flush(self) -> None:
        self.flush_calls += 1


def _cat_relation(*, value: str = "Alt", memory_id: str = "rel-1") -> dict:
    return {
        "subject": "meu gato",
        "predicate": "nome",
        "object": value,
        "memory_id": memory_id,
        "confidence": 0.95,
        "epoch": None,
        "namespace": "default",
    }


def _runtime_with_alt() -> tuple[TopologicalConversationRuntime, FakeConversationService]:
    conversation = FakeConversationService()
    conversation.next_relations = (_cat_relation(),)
    runtime = TopologicalConversationRuntime(conversation)
    ids = runtime.ingest_user("Meu gato se chama Alt.")
    assert ids == ("rel-1",)
    return runtime, conversation


def test_user_relation_from_memoria_conversation_service_becomes_factual_cognitive_state():
    runtime, conversation = _runtime_with_alt()

    assert conversation.ingest_calls == [{
        "role": "user",
        "text": "Meu gato se chama Alt.",
        "session_id": None,
        "order": None,
        "timestamp": None,
    }]
    resolution = runtime.resolve("Qual é o nome do meu gato?")
    assert resolution.hit is True
    assert resolution.unresolved is False
    assert resolution.packet is not None
    assert resolution.packet.facts[-1].value == "alt"
    assert resolution.memory_ids == ("rel-1",)

    edge = runtime.evidence.iter_evidence()[0]
    assert edge.provenance == "conversation"
    projection = runtime.bridge.iter_projections()[0]
    assert projection.epistemic_source is EpistemicSource.USER_CONFIRMED
    assert projection.promoted is True


def test_model_claim_is_quarantined_and_cannot_change_current_without_learning_gate():
    runtime, _conversation = _runtime_with_alt()
    packet = runtime.resolve("Qual é o nome do meu gato?").packet
    assert packet is not None

    validation = runtime.validate_model_response(
        packet=packet,
        response_id="response-1",
        response_text="Seu gato se chama Bob.",
        claims=(ResponseClaim("meu gato", "nome", "Bob", 0.9),),
        model_id="local-llm",
    )
    assert validation.claims[0].status is ResponseClaimStatus.CONFLICTS_WITH_CONTEXT
    candidate = validation.claims[0].evidence
    assert candidate.provenance == EpistemicSource.LLM_GENERATED.value

    candidate_projection = next(
        item for item in runtime.bridge.iter_projections()
        if item.evidence_id == candidate.evidence_id
    )
    assert candidate_projection.promoted is False
    current = runtime.store.resolve("meu gato", "nome", TemporalOperator.CURRENT)
    assert runtime.store.value_text(current.value_address) == "alt"


def test_explicit_user_learning_decision_creates_separate_trusted_evidence_and_advances_current():
    runtime, _conversation = _runtime_with_alt()
    packet = runtime.resolve("Qual é o nome do meu gato?").packet
    assert packet is not None
    validation = runtime.validate_model_response(
        packet=packet,
        response_id="response-1",
        response_text="Seu gato se chama Bob.",
        claims=(ResponseClaim("meu gato", "nome", "Bob"),),
        model_id="local-llm",
    )
    candidate = validation.claims[0].evidence

    decision = runtime.decide_learning(
        candidate_evidence_id=candidate.evidence_id,
        decision_id="confirm-1",
        accepted=True,
        validator_source=EpistemicSource.USER_CONFIRMED,
        validator_id="user",
        reason="Usuário confirmou Bob.",
    )
    assert decision.promoted_evidence_id == "learning:confirm-1"
    original = next(edge for edge in runtime.evidence.iter_evidence() if edge.evidence_id == candidate.evidence_id)
    promoted = next(edge for edge in runtime.evidence.iter_evidence() if edge.evidence_id == decision.promoted_evidence_id)
    assert original.provenance == EpistemicSource.LLM_GENERATED.value
    assert promoted.provenance == EpistemicSource.USER_CONFIRMED.value

    current = runtime.store.resolve("meu gato", "nome", TemporalOperator.CURRENT)
    assert runtime.store.value_text(current.value_address) == "bob"


def test_llm_cannot_validate_itself_through_runtime_learning_gate():
    runtime, _conversation = _runtime_with_alt()
    packet = runtime.resolve("Qual é o nome do meu gato?").packet
    assert packet is not None
    candidate = runtime.validate_model_response(
        packet=packet,
        response_id="response-1",
        response_text="Bob.",
        claims=(ResponseClaim("meu gato", "nome", "Bob"),),
        model_id="local-llm",
    ).claims[0].evidence

    with pytest.raises(ValueError, match="USER_CONFIRMED or SENSOR_OBSERVED"):
        runtime.decide_learning(
            candidate_evidence_id=candidate.evidence_id,
            decision_id="self-confirm",
            accepted=True,
            validator_source=EpistemicSource.LLM_GENERATED,
            validator_id="local-llm",
            reason="self validation",
        )


def test_duplicate_native_relation_is_idempotent_but_collision_fails_closed():
    runtime, conversation = _runtime_with_alt()
    events_before = len(runtime.store.iter_events())
    evidence_before = len(runtime.evidence.iter_evidence())

    runtime.ingest_user("Meu gato se chama Alt.")
    assert len(runtime.store.iter_events()) == events_before
    assert len(runtime.evidence.iter_evidence()) == evidence_before

    conversation.next_relations = (_cat_relation(value="Bob", memory_id="rel-1"),)
    with pytest.raises(ValueError, match="evidence_id collision"):
        runtime.ingest_user("Meu gato se chama Bob.")


def test_unresolved_user_text_creates_no_factual_relation_and_resolve_fails_closed():
    conversation = FakeConversationService()
    runtime = TopologicalConversationRuntime(conversation)

    assert runtime.ingest_user("Olá") == ()
    assert runtime.evidence.iter_evidence() == ()
    assert runtime.store.iter_events() == ()
    resolution = runtime.resolve("Qual é o nome do meu gato?")
    assert resolution.packet is None
    assert resolution.hit is False
    assert resolution.unresolved is True


def test_flush_only_delegates_to_memoria_conversation_service():
    runtime, conversation = _runtime_with_alt()
    runtime.flush()
    assert conversation.flush_calls == 1
