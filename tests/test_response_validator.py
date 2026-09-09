import pytest

from memoria_resolutiva.context_compiler import ContextCompiler
from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.evidence_temporal_bridge import EvidenceTemporalBridge, EpistemicSource
from memoria_resolutiva.learning_gate import EpistemicLearningGate
from memoria_resolutiva.response_validator import (
    ResponseClaim,
    ResponseClaimStatus,
    ResponseValidator,
)
from memoria_resolutiva.topological_memory import AddressSpace, TemporalEventStore, TemporalOperator


def _runtime():
    evidence = EvidenceCore()
    evidence.observe_relation(
        "meu gato",
        "nome",
        "Alt",
        evidence_id="u1",
        source_text="Meu gato se chama Alt.",
        provenance="USER_CONFIRMED",
        origin="user",
    )
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    bridge = EvidenceTemporalBridge(addresses, store)
    bridge.project_history(evidence)
    packet = ContextCompiler(store, projections=bridge.iter_projections()).compile("Qual é o nome do meu gato?")
    return evidence, addresses, store, bridge, packet


def test_supported_model_claim_remains_llm_generated_and_does_not_mutate_temporal_state():
    evidence, _addresses, store, bridge, packet = _runtime()
    before_events = store.iter_events()
    validator = ResponseValidator(evidence)

    result = validator.validate(
        packet=packet,
        response_id="r1",
        response_text="Seu gato se chama Alt.",
        claims=(ResponseClaim("meu gato", "nome", "Alt", 0.99),),
        model_id="local-llm",
    )

    assert result.claims[0].status is ResponseClaimStatus.SUPPORTED_BY_CONTEXT
    assert result.claims[0].evidence.provenance == "LLM_GENERATED"
    assert store.iter_events() == before_events

    projection = bridge.project_edge(result.claims[0].evidence)
    assert projection.promoted is False
    assert projection.epistemic_source is EpistemicSource.LLM_GENERATED
    current = store.resolve("meu gato", "nome", TemporalOperator.CURRENT)
    assert store.value_text(current.value_address) == "alt"


def test_conflicting_model_claim_is_classified_and_quarantined():
    evidence, _addresses, store, bridge, packet = _runtime()
    validator = ResponseValidator(evidence)

    result = validator.validate(
        packet=packet,
        response_id="r2",
        response_text="Seu gato se chama Bob.",
        claims=(ResponseClaim("meu gato", "nome", "Bob", 0.95),),
        model_id="cloud-llm",
    )

    assert result.claims[0].status is ResponseClaimStatus.CONFLICTS_WITH_CONTEXT
    projection = bridge.project_edge(result.claims[0].evidence)
    assert projection.promoted is False
    current = store.resolve("meu gato", "nome", TemporalOperator.CURRENT)
    assert store.value_text(current.value_address) == "alt"


def test_unverified_model_claim_is_not_treated_as_fact():
    evidence, _addresses, store, bridge, packet = _runtime()
    validator = ResponseValidator(evidence)

    result = validator.validate(
        packet=packet,
        response_id="r3",
        response_text="Seu carro é azul.",
        claims=(ResponseClaim("meu carro", "cor", "azul", 0.8),),
        model_id="cloud-llm",
    )

    assert result.claims[0].status is ResponseClaimStatus.UNVERIFIED
    assert bridge.project_edge(result.claims[0].evidence).promoted is False
    assert store.resolve("meu carro", "cor", TemporalOperator.CURRENT).value_address is None


def test_external_validation_can_promote_separate_trusted_evidence_after_response_validation():
    evidence, addresses, store, bridge, packet = _runtime()
    validator = ResponseValidator(evidence)
    result = validator.validate(
        packet=packet,
        response_id="r4",
        response_text="Seu gato se chama Bob.",
        claims=(ResponseClaim("meu gato", "nome", "Bob", 0.9),),
        model_id="cloud-llm",
    )
    candidate = result.claims[0].evidence
    bridge.project_edge(candidate)

    gate = EpistemicLearningGate(evidence)
    decision = gate.decide(
        candidate,
        decision_id="confirm-r4",
        accepted=True,
        validator_source=EpistemicSource.USER_CONFIRMED,
        validator_id="user",
        reason="Usuário confirmou a correção.",
    )
    promoted = next(
        edge
        for edge in evidence.evidence_history(namespace=candidate.namespace)
        if edge.evidence_id == decision.promoted_evidence_id
    )
    projection = bridge.project_edge(promoted)

    assert candidate.provenance == "LLM_GENERATED"
    assert projection.promoted is True
    current = store.resolve("meu gato", "nome", TemporalOperator.CURRENT)
    assert store.value_text(current.value_address) == "bob"
    assert addresses.reconstruct_raw(projection.temporal_event.raw_memory_address) == "Seu gato se chama Bob."


def test_response_id_is_idempotency_boundary():
    evidence, _addresses, _store, _bridge, packet = _runtime()
    validator = ResponseValidator(evidence)
    kwargs = dict(
        packet=packet,
        response_id="dup",
        response_text="Seu gato se chama Alt.",
        claims=(ResponseClaim("meu gato", "nome", "Alt"),),
        model_id="local",
    )
    validator.validate(**kwargs)
    with pytest.raises(ValueError, match="already been validated"):
        validator.validate(**kwargs)


def test_response_validator_restore_preserves_idempotency_boundary():
    evidence, _addresses, _store, _bridge, packet = _runtime()
    validator = ResponseValidator(evidence)
    validator.restore_response_ids(("r-old",))

    with pytest.raises(ValueError, match="already been validated"):
        validator.validate(
            packet=packet,
            response_id="r-old",
            response_text="Seu gato se chama Alt.",
            claims=(ResponseClaim("meu gato", "nome", "Alt"),),
            model_id="local",
        )


def test_invalid_claim_confidence_fails_closed_before_writing_evidence():
    evidence, _addresses, _store, _bridge, packet = _runtime()
    before = evidence.evidence_history()
    validator = ResponseValidator(evidence)

    with pytest.raises(ValueError, match="confidence"):
        validator.validate(
            packet=packet,
            response_id="bad",
            response_text="texto",
            claims=(ResponseClaim("x", "y", "z", 1.5),),
            model_id="local",
        )

    assert evidence.evidence_history() == before
