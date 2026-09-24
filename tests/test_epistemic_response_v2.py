from memoria_resolutiva.context_compiler_v2 import CognitiveContextPacketV2
from memoria_resolutiva.epistemic_response_v2 import (
    EpistemicDecisionLedgerV2,
    EpistemicResponseValidatorV2,
    make_claim_candidate_v2,
)


def _packet(*, status="resolved", resolved=(30,), competing=()):
    return CognitiveContextPacketV2(
        version=2,
        hierarchy_id="r11",
        addresses=(10, 20),
        status=status,
        resolved_state=tuple(resolved),
        competing_states=tuple(competing),
        trajectory_ids=("t:1",),
        provenance_ids=("p:1",),
        equivalence_witness_ids=(),
        conflicts=(),
        source_tier="direct-attractor" if status != "unresolved" else "none",
        terminal=status == "terminal",
        bounded_out=False,
        uncertainty="resolved" if status == "resolved" else "insufficient-evidence",
    )


def test_r11_claim_is_separately_identifiable_and_validation_does_not_mutate_memory():
    packet = _packet()
    before = packet
    claim = make_claim_candidate_v2(
        response_id="response:1",
        claim_index=0,
        asserted_addresses=[30],
        provenance_ids=["model:output:1"],
        surface_ref="response:1#claim:0",
    )

    result = EpistemicResponseValidatorV2.validate(claim, packet)

    assert claim.claim_id.startswith("epistemic-claim:")
    assert result.status == "consistent"
    assert result.truth_assessment is False
    assert result.memory_mutated is False
    assert packet == before


def test_r11_validator_preserves_competing_and_unsupported_claims():
    competing = make_claim_candidate_v2(
        response_id="response:2", claim_index=0, asserted_addresses=[40]
    )
    unsupported = make_claim_candidate_v2(
        response_id="response:2", claim_index=1, asserted_addresses=[99]
    )
    packet = _packet(status="ambiguous", resolved=(), competing=(30, 40))

    assert EpistemicResponseValidatorV2.validate(competing, packet).status == "competing"
    assert EpistemicResponseValidatorV2.validate(unsupported, packet).status == "unsupported"


def test_r11_unresolved_memory_does_not_turn_model_output_into_truth():
    claim = make_claim_candidate_v2(
        response_id="response:3", claim_index=0, asserted_addresses=[30]
    )
    result = EpistemicResponseValidatorV2.validate(
        claim, _packet(status="unresolved", resolved=(), competing=())
    )

    assert result.status == "unresolved"
    assert result.truth_assessment is False


def test_r11_explicit_decision_is_separate_from_immutable_candidate_and_survives_restart(tmp_path):
    claim = make_claim_candidate_v2(
        response_id="response:4", claim_index=0, asserted_addresses=[30]
    )
    validation = EpistemicResponseValidatorV2.validate(claim, _packet())
    original = claim
    path = tmp_path / "epistemic-decisions.jsonl"

    ledger = EpistemicDecisionLedgerV2(path)
    first = ledger.record(
        claim,
        validation,
        sequence=7,
        action="accept",
        evidence_ids=["human:approval:1"],
        rationale_ref="review:7",
    )
    repeated = ledger.record(
        claim,
        validation,
        sequence=7,
        action="accept",
        evidence_ids=["human:approval:1"],
        rationale_ref="review:7",
    )

    assert repeated == first
    assert claim == original
    assert len(ledger.snapshot()) == 1

    reopened = EpistemicDecisionLedgerV2(path)
    assert reopened.snapshot() == (first,)
    again = reopened.record(
        claim,
        validation,
        sequence=7,
        action="accept",
        evidence_ids=["human:approval:1"],
        rationale_ref="review:7",
    )
    assert again == first
    assert len(reopened.snapshot()) == 1
