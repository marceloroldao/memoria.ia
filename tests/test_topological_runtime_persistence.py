from __future__ import annotations

import os
from pathlib import Path

import pytest

from memoria_resolutiva.bdr_store import native_bdr_available
from memoria_resolutiva.conversation_contract import ConversationIngestResult, ConversationResolveResult
from memoria_resolutiva.evidence_temporal_bridge import EpistemicSource
from memoria_resolutiva.response_validator import ResponseClaim
from memoria_resolutiva.topological_conversation_runtime import TopologicalConversationRuntime
from memoria_resolutiva.topological_memory import TemporalOperator
from memoria_resolutiva.topological_runtime_persistence import TopologicalRuntimePersistence


class FakeConversationService:
    def __init__(self) -> None:
        self.next_memory_ids: tuple[str, ...] = ("turn-1",)
        self.next_relations: tuple[dict, ...] = ()

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
        return ConversationIngestResult(
            self.next_memory_ids,
            self.next_relations,
            not self.next_relations,
        )

    def resolve(self, *, query: str, session_id: str | None = None) -> ConversationResolveResult:
        raise AssertionError("runtime persistence test must resolve through ContextCompiler")


def _require_bdr() -> str:
    library_path = os.environ.get("BDR_ATOMIC_LIB")
    if not library_path or not native_bdr_available():
        pytest.skip("real BDR shared ABI + native EvidenceCore binding are required")
    return library_path


def _runtime_with_confirmed_model_correction() -> tuple[TopologicalConversationRuntime, str]:
    conversation = FakeConversationService()
    conversation.next_relations = ({
        "subject": "meu gato",
        "predicate": "nome",
        "object": "Alt",
        "memory_id": "rel-alt",
        "confidence": 0.95,
        "epoch": None,
        "namespace": "default",
    },)
    runtime = TopologicalConversationRuntime(conversation)
    runtime.ingest_user("Meu gato se chama Alt.")
    packet = runtime.resolve("Qual é o nome do meu gato?").packet
    assert packet is not None

    validation = runtime.validate_model_response(
        packet=packet,
        response_id="response-1",
        response_text="Seu gato se chama Bob.",
        claims=(ResponseClaim("meu gato", "nome", "Bob"),),
        model_id="local-llm",
    )
    candidate_id = validation.claims[0].evidence.evidence_id
    runtime.decide_learning(
        candidate_evidence_id=candidate_id,
        decision_id="confirm-1",
        accepted=True,
        validator_source=EpistemicSource.USER_CONFIRMED,
        validator_id="user",
        reason="Usuário confirmou Bob.",
    )
    return runtime, candidate_id


def test_real_bdr_runtime_checkpoint_reopens_full_cognitive_boundary(tmp_path: Path):
    library_path = _require_bdr()
    runtime, candidate_id = _runtime_with_confirmed_model_correction()
    persistence = TopologicalRuntimePersistence(
        tmp_path / "runtime",
        atomic_library_path=library_path,
        evidence_backend="bdr",
        evidence_allow_fallback=False,
    )

    checkpoint = persistence.checkpoint(runtime)
    assert checkpoint.generation == 1
    assert checkpoint.evidence_receipt.backend == "bdr"
    assert checkpoint.topology.bdr_sequence >= 1
    assert checkpoint.epistemic.bdr_sequence >= checkpoint.topology.bdr_sequence

    restarted = persistence.open(FakeConversationService())
    current = restarted.store.resolve("meu gato", "nome", TemporalOperator.CURRENT)
    assert restarted.store.value_text(current.value_address) == "bob"
    packet = restarted.resolve("Qual é o nome do meu gato?").packet
    assert packet is not None
    assert packet.facts[-1].value == "bob"

    candidate = next(edge for edge in restarted.evidence.iter_evidence() if edge.evidence_id == candidate_id)
    assert candidate.provenance == EpistemicSource.LLM_GENERATED.value
    assert restarted.validator.iter_response_ids() == ("response-1",)
    assert tuple(decision.decision_id for decision in restarted.gate.iter_decisions()) == ("confirm-1",)

    with pytest.raises(ValueError, match="already been validated"):
        restarted.validate_model_response(
            packet=packet,
            response_id="response-1",
            response_text="Bob.",
            claims=(ResponseClaim("meu gato", "nome", "Bob"),),
            model_id="local-llm",
        )
    with pytest.raises(ValueError, match="already been applied"):
        restarted.decide_learning(
            candidate_evidence_id=candidate_id,
            decision_id="confirm-1",
            accepted=False,
            validator_source=EpistemicSource.USER_CONFIRMED,
            validator_id="user",
            reason="duplicate",
        )


def test_incomplete_next_generation_does_not_replace_committed_runtime(tmp_path: Path):
    library_path = _require_bdr()
    runtime, _candidate_id = _runtime_with_confirmed_model_correction()
    persistence = TopologicalRuntimePersistence(
        tmp_path / "runtime",
        atomic_library_path=library_path,
        evidence_backend="bdr",
        evidence_allow_fallback=False,
    )
    persistence.checkpoint(runtime)

    # Simulate a crash after creating staging state but before CURRENT replacement.
    staging = persistence.root / ".generation-00000000000000000002.tmp"
    staging.mkdir(parents=True)
    (staging / "partial").write_text("incomplete", "utf-8")

    restarted = persistence.open(FakeConversationService())
    current = restarted.store.resolve("meu gato", "nome", TemporalOperator.CURRENT)
    assert restarted.store.value_text(current.value_address) == "bob"


def test_second_checkpoint_advances_generation_and_becomes_current(tmp_path: Path):
    library_path = _require_bdr()
    runtime, _candidate_id = _runtime_with_confirmed_model_correction()
    persistence = TopologicalRuntimePersistence(
        tmp_path / "runtime",
        atomic_library_path=library_path,
        evidence_backend="bdr",
        evidence_allow_fallback=False,
    )
    first = persistence.checkpoint(runtime)
    assert first.generation == 1

    conversation = runtime.conversation
    assert isinstance(conversation, FakeConversationService)
    conversation.next_memory_ids = ("turn-2",)
    conversation.next_relations = ({
        "subject": "meu carro",
        "predicate": "cor",
        "object": "azul",
        "memory_id": "rel-car-blue",
        "confidence": 0.97,
        "epoch": None,
        "namespace": "default",
    },)
    runtime.ingest_user("Meu carro é azul.")
    second = persistence.checkpoint(runtime)
    assert second.generation == 2

    restarted = persistence.open(FakeConversationService())
    current = restarted.store.resolve("meu carro", "cor", TemporalOperator.CURRENT)
    assert restarted.store.value_text(current.value_address) == "azul"
