import pytest

from memoria_resolutiva.recovery_quorum_v122 import RecoveryQuorumMemoryV122


def _memory(threshold=2):
    m = RecoveryQuorumMemoryV122()
    m.add_trusted_issuer("root")
    m.attest_authority("authority-a", issuer_id="root", attestation_id="att-1")
    m.bind_initial_authority_key(
        "authority-a", key_id="key-1", issuer_id="root", binding_id="bind-1"
    )
    m.configure_recovery_quorum(
        "authority-a", approver_ids=("guardian-1", "guardian-2", "guardian-3"), threshold=threshold
    )
    m.report_key_compromise(
        "authority-a", key_id="key-1", issuer_id="root", compromise_id="comp-1", compromised_at_epoch=2
    )
    return m


def _approve(m, guardian, approval):
    return m.approve_recovery(
        "authority-a",
        compromised_key_id="key-1",
        replacement_key_id="key-2",
        approver_id=guardian,
        approval_id=approval,
        recovery_evidence_id="evidence-1",
        effective_epoch=3,
    )


def test_single_approver_cannot_satisfy_two_of_three_quorum():
    m = _memory()
    _approve(m, "guardian-1", "ap-1")
    with pytest.raises(ValueError):
        m.recover_authority_key(
            "authority-a", compromised_key_id="key-1", replacement_key_id="key-2",
            issuer_id="root", recovery_id="rec-1", recovery_evidence_id="evidence-1",
            effective_epoch=3,
        )


def test_two_distinct_approvers_satisfy_quorum():
    m = _memory()
    _approve(m, "guardian-1", "ap-1")
    _approve(m, "guardian-2", "ap-2")
    m.recover_authority_key(
        "authority-a", compromised_key_id="key-1", replacement_key_id="key-2",
        issuer_id="root", recovery_id="rec-1", recovery_evidence_id="evidence-1",
        effective_epoch=3,
    )
    assert m.active_authority_key("authority-a", epoch=3) == "key-2"


def test_same_approver_cannot_count_twice_for_same_tuple():
    m = _memory()
    _approve(m, "guardian-1", "ap-1")
    with pytest.raises(ValueError):
        _approve(m, "guardian-1", "ap-2")


def test_unauthorized_approver_is_rejected():
    m = _memory()
    with pytest.raises(ValueError):
        _approve(m, "outsider", "ap-x")


def test_approvals_for_different_replacement_do_not_mix():
    m = _memory()
    _approve(m, "guardian-1", "ap-1")
    m.approve_recovery(
        "authority-a", compromised_key_id="key-1", replacement_key_id="key-x",
        approver_id="guardian-2", approval_id="ap-2", recovery_evidence_id="evidence-1",
        effective_epoch=3,
    )
    assert m.recovery_quorum_count(
        "authority-a", compromised_key_id="key-1", replacement_key_id="key-2",
        recovery_evidence_id="evidence-1",
    ) == 1


def test_recovery_policy_is_immutable():
    m = _memory()
    with pytest.raises(ValueError):
        m.configure_recovery_quorum(
            "authority-a", approver_ids=("guardian-1", "guardian-2"), threshold=1
        )


def test_v121_history_preserved_after_quorum_recovery():
    m = _memory()
    _approve(m, "guardian-1", "ap-1")
    _approve(m, "guardian-2", "ap-2")
    m.recover_authority_key(
        "authority-a", compromised_key_id="key-1", replacement_key_id="key-2",
        issuer_id="root", recovery_id="rec-1", recovery_evidence_id="evidence-1",
        effective_epoch=3,
    )
    assert m.active_authority_key("authority-a", epoch=1) == "key-1"
    assert m.active_authority_key("authority-a", epoch=2) is None
    assert m.active_authority_key("authority-a", epoch=3) == "key-2"
