import pytest

from memoria_resolutiva.context_compiler_v2 import CognitiveContextPacketV2
from memoria_resolutiva.epistemic_response_v2 import (
    EpistemicDecisionLedgerV2,
    EpistemicResponseValidatorV2,
    make_claim_candidate_v2,
)
from memoria_resolutiva.learning_admission_v2 import (
    LearningAdmissionAdapterV2,
    LearningAdmissionJournalV2,
)
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex


def _packet(*, status="unresolved", resolved=(), competing=()):
    return CognitiveContextPacketV2(
        version=2,
        hierarchy_id="r11-learning",
        addresses=(10, 20),
        status=status,
        resolved_state=tuple(resolved),
        competing_states=tuple(competing),
        trajectory_ids=(),
        provenance_ids=(),
        equivalence_witness_ids=(),
        conflicts=(),
        source_tier="none" if status == "unresolved" else "direct-attractor",
        terminal=False,
        bounded_out=False,
        uncertainty="insufficient-evidence" if status == "unresolved" else "competing-evidence",
    )


def _decision(tmp_path, *, action="accept", evidence_ids=("human:approval:1",), status="unresolved"):
    claim = make_claim_candidate_v2(
        response_id="response:learning",
        claim_index=0,
        asserted_addresses=[10, 20, 30],
        provenance_ids=["model:output:learning"],
    )
    validation = EpistemicResponseValidatorV2.validate(
        claim,
        _packet(status=status, competing=(30, 40) if status == "ambiguous" else ()),
    )
    decision = EpistemicDecisionLedgerV2(tmp_path / "decisions.jsonl").record(
        claim,
        validation,
        sequence=4,
        action=action,
        evidence_ids=evidence_ids,
        rationale_ref="review:4",
    )
    return claim, decision


def test_r11_learning_admission_requires_explicit_accept_and_evidence(tmp_path):
    journal = LearningAdmissionJournalV2(tmp_path / "admissions.jsonl")

    claim, rejected = _decision(tmp_path, action="reject")
    with pytest.raises(ValueError, match="explicit accept"):
        journal.append(claim, rejected, hierarchy_id="r11-learning", sequence=5)

    claim2 = make_claim_candidate_v2(
        response_id="response:no-evidence",
        claim_index=0,
        asserted_addresses=[1, 2, 3],
    )
    validation2 = EpistemicResponseValidatorV2.validate(claim2, _packet())
    accepted_without_evidence = EpistemicDecisionLedgerV2(
        tmp_path / "decisions-no-evidence.jsonl"
    ).record(
        claim2,
        validation2,
        sequence=5,
        action="accept",
    )
    with pytest.raises(ValueError, match="evidence_ids"):
        journal.append(
            claim2,
            accepted_without_evidence,
            hierarchy_id="r11-learning",
            sequence=6,
        )


def test_r11_learning_admission_can_preserve_competing_evidence(tmp_path):
    claim, decision = _decision(tmp_path, status="ambiguous")
    journal = LearningAdmissionJournalV2(tmp_path / "admissions.jsonl")
    index = StructuralTrajectoryIndex()
    adapter = LearningAdmissionAdapterV2(journal, index)

    admission, trajectory = adapter.admit(
        claim,
        decision,
        hierarchy_id="r11-learning",
        sequence=5,
    )

    assert admission.validator_status == "competing"
    assert admission.evidence_ids == ("human:approval:1",)
    assert trajectory.addresses == claim.asserted_addresses
    assert trajectory.observation_id == admission.admission_id
    assert trajectory.source_id.startswith("epistemic-admission:")
    assert index.count == 1


def test_r11_learning_admission_is_idempotent_and_restart_replay_safe(tmp_path):
    claim, decision = _decision(tmp_path)
    path = tmp_path / "admissions.jsonl"
    journal = LearningAdmissionJournalV2(path)
    index = StructuralTrajectoryIndex()
    adapter = LearningAdmissionAdapterV2(journal, index)

    first_admission, first_trajectory = adapter.admit(
        claim,
        decision,
        hierarchy_id="r11-learning",
        sequence=5,
    )
    second_admission, second_trajectory = adapter.admit(
        claim,
        decision,
        hierarchy_id="r11-learning",
        sequence=5,
    )

    assert second_admission == first_admission
    assert second_trajectory == first_trajectory
    assert len(journal.snapshot()) == 1
    assert index.count == 1

    reopened = LearningAdmissionJournalV2(path)
    rebuilt = StructuralTrajectoryIndex()
    replay = LearningAdmissionAdapterV2(reopened, rebuilt)
    assert replay.replay() == 1
    assert rebuilt.snapshot() == (first_trajectory,)
    assert replay.replay() == 0


def test_r11_learning_admission_does_not_rewrite_claim_or_decision(tmp_path):
    claim, decision = _decision(tmp_path)
    claim_before = claim
    decision_before = decision
    adapter = LearningAdmissionAdapterV2(
        LearningAdmissionJournalV2(tmp_path / "admissions.jsonl"),
        StructuralTrajectoryIndex(),
    )

    adapter.admit(claim, decision, hierarchy_id="r11-learning", sequence=5)

    assert claim == claim_before
    assert decision == decision_before
