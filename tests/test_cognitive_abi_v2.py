from memoria_resolutiva.cognitive_abi_v2 import CognitiveAbiEnvelopeV2
from memoria_resolutiva.context_compiler_v2 import CognitiveContextPacketV2
from memoria_resolutiva.epistemic_response_v2 import (
    EpistemicDecisionLedgerV2,
    EpistemicResponseValidatorV2,
    make_claim_candidate_v2,
)
from memoria_resolutiva.learning_admission_v2 import (
    LearningAdmissionJournalV2,
)


def _packet(*, status="resolved"):
    return CognitiveContextPacketV2(
        version=2,
        hierarchy_id="abi",
        addresses=(10, 20),
        status=status,
        resolved_state=(30,) if status == "resolved" else (),
        competing_states=(),
        trajectory_ids=("t:1",),
        provenance_ids=("p:1",),
        equivalence_witness_ids=(),
        conflicts=(),
        source_tier="direct-attractor" if status == "resolved" else "none",
        terminal=False,
        bounded_out=False,
        uncertainty="resolved" if status == "resolved" else "insufficient-evidence",
    )


def test_r12_local_memory_origin_is_explicit_and_model_free():
    envelope = CognitiveAbiEnvelopeV2.from_context(
        _packet(),
        request_id="req:1",
        session_id="session:1",
        execution_plane="local",
        memory_plane="local",
    )

    assert envelope.origin.response_origin == "local-memory"
    assert envelope.origin.memory_used is True
    assert envelope.origin.model_used is False
    assert envelope.origin.llm_calls == 0


def test_r12_server_memory_origin_is_distinguishable_from_local():
    envelope = CognitiveAbiEnvelopeV2.from_context(
        _packet(),
        request_id="req:2",
        execution_plane="server",
        memory_plane="server",
    )

    assert envelope.origin.response_origin == "server-memory"
    assert envelope.origin.execution_plane == "server"
    assert envelope.origin.memory_plane == "server"


def test_r12_hybrid_origin_shows_local_memory_plus_server_model():
    envelope = CognitiveAbiEnvelopeV2.from_context(
        _packet(),
        request_id="req:3",
        execution_plane="local",
        memory_plane="local",
        language_plane="server",
        external_calls=1,
        llm_calls=1,
    )

    assert envelope.origin.response_origin == "hybrid-local-memory+server-model"
    assert envelope.origin.model_used is True
    assert envelope.origin.external_calls == 1
    assert envelope.origin.llm_calls == 1


def test_r12_epistemic_lineage_is_explicit_without_embedding_mutable_objects(tmp_path):
    packet = _packet()
    claim = make_claim_candidate_v2(
        response_id="response:abi",
        claim_index=0,
        asserted_addresses=[30],
    )
    validation = EpistemicResponseValidatorV2.validate(claim, packet)
    decision = EpistemicDecisionLedgerV2(tmp_path / "decisions.jsonl").record(
        claim,
        validation,
        sequence=1,
        action="accept",
        evidence_ids=["user:confirmation:1"],
    )
    admission = LearningAdmissionJournalV2(tmp_path / "admissions.jsonl").append(
        claim,
        decision,
        hierarchy_id="abi",
        sequence=2,
    )

    envelope = CognitiveAbiEnvelopeV2.from_context(
        packet,
        request_id="req:4",
        execution_plane="server",
        memory_plane="server",
        claim=claim,
        validation=validation,
        decision=decision,
        admission=admission,
    )

    assert envelope.epistemic.claim_id == claim.claim_id
    assert envelope.epistemic.validation_status == "consistent"
    assert envelope.epistemic.decision_id == decision.decision_id
    assert envelope.epistemic.decision_action == "accept"
    assert envelope.epistemic.admission_id == admission.admission_id


def test_r12_json_round_trip_is_deterministic_for_native_mobile_server_boundary():
    envelope = CognitiveAbiEnvelopeV2.from_context(
        _packet(),
        request_id="req:5",
        session_id="session:5",
        execution_plane="local",
        memory_plane="local",
    )

    payload = envelope.to_json()
    reopened = CognitiveAbiEnvelopeV2.from_json(payload)

    assert reopened == envelope
    assert reopened.to_json() == payload


def test_r12_unresolved_memory_reports_unresolved_without_faking_origin():
    envelope = CognitiveAbiEnvelopeV2.from_context(
        _packet(status="unresolved"),
        request_id="req:6",
        execution_plane="local",
        memory_plane="local",
    )

    assert envelope.origin.response_origin == "unresolved"
    assert envelope.origin.memory_used is False
    assert envelope.origin.model_used is False
