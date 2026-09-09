import pytest

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.evidence_temporal_bridge import EpistemicSource, EvidenceTemporalBridge
from memoria_resolutiva.learning_gate import EpistemicLearningGate
from memoria_resolutiva.topological_memory import AddressSpace, TemporalEventStore, TemporalOperator


def _llm_candidate(evidence: EvidenceCore):
    return evidence.observe_relation(
        "minha camisa",
        "cor",
        "vermelha",
        evidence_id="llm-candidate-1",
        source_text="Sua camisa provavelmente é vermelha.",
        provenance="LLM_GENERATED",
        origin="assistant",
        confidence=0.99,
    )


def test_rejected_llm_candidate_never_creates_trusted_evidence():
    evidence = EvidenceCore()
    candidate = _llm_candidate(evidence)
    gate = EpistemicLearningGate(evidence)

    decision = gate.decide(
        candidate,
        decision_id="d1",
        accepted=False,
        validator_source=EpistemicSource.USER_CONFIRMED,
        validator_id="user",
        reason="Usuário negou a sugestão.",
    )

    assert decision.accepted is False
    assert decision.promoted_evidence_id is None
    assert [edge.evidence_id for edge in evidence.evidence_history()] == ["llm-candidate-1"]


def test_accepted_llm_candidate_creates_separate_user_confirmed_evidence():
    evidence = EvidenceCore()
    candidate = _llm_candidate(evidence)
    gate = EpistemicLearningGate(evidence)

    decision = gate.decide(
        candidate,
        decision_id="d2",
        accepted=True,
        validator_source=EpistemicSource.USER_CONFIRMED,
        validator_id="user",
        reason="Usuário confirmou a cor.",
    )

    rows = evidence.evidence_history()
    assert len(rows) == 2
    assert rows[0].evidence_id == "llm-candidate-1"
    assert rows[0].provenance == "LLM_GENERATED"
    promoted = rows[1]
    assert promoted.evidence_id == decision.promoted_evidence_id
    assert promoted.provenance == "USER_CONFIRMED"
    assert "candidate=llm-candidate-1" in promoted.origin
    assert "candidate_source=LLM_GENERATED" in promoted.origin


def test_only_validated_edge_changes_temporal_current_after_learning_gate():
    evidence = EvidenceCore()
    candidate = _llm_candidate(evidence)
    gate = EpistemicLearningGate(evidence)
    gate.decide(
        candidate,
        decision_id="d3",
        accepted=True,
        validator_source=EpistemicSource.USER_CONFIRMED,
        validator_id="user",
        reason="Confirmação explícita.",
    )
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    bridge = EvidenceTemporalBridge(addresses, store)

    batch = bridge.project_history(evidence)

    assert len(batch.promoted) == 1
    assert len(batch.quarantined) == 1
    current = store.resolve("minha camisa", "cor", TemporalOperator.CURRENT)
    assert store.value_text(current.value_address) == "vermelha"
    assert tuple(event.source for event in store.iter_events()) == ("USER_CONFIRMED",)


def test_system_or_llm_cannot_act_as_learning_validator():
    evidence = EvidenceCore()
    candidate = _llm_candidate(evidence)
    gate = EpistemicLearningGate(evidence)

    with pytest.raises(ValueError):
        gate.decide(
            candidate,
            decision_id="d4",
            accepted=True,
            validator_source=EpistemicSource.LLM_GENERATED,
            validator_id="assistant",
            reason="self validation",
        )

    with pytest.raises(ValueError):
        gate.decide(
            candidate,
            decision_id="d5",
            accepted=True,
            validator_source=EpistemicSource.SYSTEM_INFERRED,
            validator_id="rule-engine",
            reason="automatic inference",
        )


def test_sensor_validation_can_create_trusted_observation_without_reclassifying_candidate():
    evidence = EvidenceCore()
    candidate = evidence.observe_relation(
        "sensor sala",
        "temperatura",
        "26",
        evidence_id="model-temp",
        source_text="Modelo estimou 26 graus.",
        provenance="LLM_GENERATED",
        origin="model",
    )
    gate = EpistemicLearningGate(evidence)

    gate.decide(
        candidate,
        decision_id="sensor-confirm-1",
        accepted=True,
        validator_source=EpistemicSource.SENSOR_OBSERVED,
        validator_id="sensor-42",
        reason="Leitura física confirmou o valor.",
    )

    original, confirmed = evidence.evidence_history()
    assert original.provenance == "LLM_GENERATED"
    assert confirmed.provenance == "SENSOR_OBSERVED"
    assert "candidate=model-temp" in confirmed.origin


def test_learning_decision_id_is_idempotency_boundary():
    evidence = EvidenceCore()
    candidate = _llm_candidate(evidence)
    gate = EpistemicLearningGate(evidence)
    kwargs = dict(
        decision_id="unique-decision",
        accepted=False,
        validator_source=EpistemicSource.USER_CONFIRMED,
        validator_id="user",
        reason="rejeitado",
    )

    gate.decide(candidate, **kwargs)
    with pytest.raises(ValueError):
        gate.decide(candidate, **kwargs)
