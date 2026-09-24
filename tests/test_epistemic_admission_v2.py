import pytest

from memoria_resolutiva.context_compiler_v2 import CognitiveContextPacketV2
from memoria_resolutiva.epistemic_admission_v2 import EpistemicEvidenceAdmissionLedgerV2
from memoria_resolutiva.epistemic_response_v2 import (
    EpistemicDecisionLedgerV2,
    EpistemicResponseValidatorV2,
    make_claim_candidate_v2,
)
from memoria_resolutiva.structural_observation import StructuralObservationStore


def _packet():
    return CognitiveContextPacketV2(
        version=2,
        hierarchy_id="r11-admission",
        addresses=(10, 20),
        status="resolved",
        resolved_state=(30,),
        competing_states=(),
        trajectory_ids=("t:1",),
        provenance_ids=("p:1",),
        equivalence_witness_ids=(),
        conflicts=(),
        source_tier="direct-attractor",
        terminal=False,
        bounded_out=False,
        uncertainty="resolved",
    )


def _accepted(tmp_path, *, action="accept"):
    claim = make_claim_candidate_v2(
        response_id="response:admission",
        claim_index=0,
        asserted_addresses=[30],
        provenance_ids=["model:output"],
    )
    validation = EpistemicResponseValidatorV2.validate(claim, _packet())
    decision = EpistemicDecisionLedgerV2(tmp_path / "decisions.jsonl").record(
        claim,
        validation,
        sequence=1,
        action=action,
        evidence_ids=["human:review:1"],
    )
    return claim, decision


def _event(trail):
    return {
        "version": 1,
        "source_id": "independent-observation",
        "sequence": 9,
        "byte_offset": 0,
        "byte_length": 1,
        "trail": list(trail),
        "relation_ids": [],
        "signature": "0123456789abcdef",
        "resolution": 1,
    }


def test_r11_accept_creates_admission_but_not_memory_observation(tmp_path):
    claim, decision = _accepted(tmp_path)
    observations = StructuralObservationStore(tmp_path / "observations", backend="sqlite")
    ledger = EpistemicEvidenceAdmissionLedgerV2(tmp_path / "admissions.jsonl")

    before = observations.count
    admission = ledger.admit(claim, decision)

    assert admission.claim_id == claim.claim_id
    assert admission.decision_id == decision.decision_id
    assert admission.asserted_addresses == (30,)
    assert admission.memory_observation_created is False
    assert observations.count == before == 0


def test_r11_reject_or_defer_cannot_be_admitted(tmp_path):
    for action in ("reject", "defer"):
        root = tmp_path / action
        claim, decision = _accepted(root, action=action)
        ledger = EpistemicEvidenceAdmissionLedgerV2(root / "admissions.jsonl")
        with pytest.raises(ValueError, match="explicit accept"):
            ledger.admit(claim, decision)


def test_r11_admission_can_bind_only_to_independent_matching_observation(tmp_path):
    claim, decision = _accepted(tmp_path)
    ledger = EpistemicEvidenceAdmissionLedgerV2(tmp_path / "admissions.jsonl")
    admission = ledger.admit(claim, decision)
    observations = StructuralObservationStore(tmp_path / "observations", backend="sqlite")

    envelope, duplicate = observations.append(
        _event([30]),
        provenance={"kind": "independent-observation", "hierarchy_id": "r11-admission"},
    )
    assert duplicate is False

    binding = ledger.bind_observation(admission, observations, envelope["observation_id"])

    assert binding.observation_id == envelope["observation_id"]
    assert binding.asserted_addresses == binding.observation_trail == (30,)
    assert binding.memory_observation_created is False
    assert observations.count == 1


def test_r11_admission_rejects_mismatched_observation_and_survives_restart(tmp_path):
    claim, decision = _accepted(tmp_path)
    path = tmp_path / "admissions.jsonl"
    ledger = EpistemicEvidenceAdmissionLedgerV2(path)
    admission = ledger.admit(claim, decision)
    observations = StructuralObservationStore(tmp_path / "observations", backend="sqlite")
    envelope, _ = observations.append(
        _event([99]),
        provenance={"kind": "independent-observation", "hierarchy_id": "r11-admission"},
    )

    with pytest.raises(ValueError, match="does not match"):
        ledger.bind_observation(admission, observations, envelope["observation_id"])

    reopened = EpistemicEvidenceAdmissionLedgerV2(path)
    assert reopened.admissions() == (admission,)
    assert reopened.bindings() == ()
