import pytest

from memoria_resolutiva.controller_transfer_revocation_v126 import (
    ControllerTransferRevocationMemoryV126,
)


def _memory():
    m = ControllerTransferRevocationMemoryV126()
    m.bind_guardian_controller("target", controller_id="org-owner")
    m.bind_guardian_controller("g1", controller_id="org-a")
    m.bind_guardian_controller("g2", controller_id="org-b")
    m.configure_controller_transfer_quorum(
        "target", approver_ids=["g1", "g2"], threshold=2
    )
    m.set_policy_epoch(1)
    return m


def _approve(m, approver, approval_id):
    return m.approve_controller_transfer(
        "target",
        current_controller_id="org-owner",
        new_controller_id="org-new",
        approver_id=approver,
        approval_id=approval_id,
        transfer_evidence_id="ev-1",
        effective_epoch=1,
    )


def test_revoked_approval_no_longer_counts_toward_quorum():
    m = _memory()
    _approve(m, "g1", "a1")
    _approve(m, "g2", "a2")
    assert m.controller_transfer_quorum_count(
        "target",
        current_controller_id="org-owner",
        new_controller_id="org-new",
        transfer_evidence_id="ev-1",
        effective_epoch=1,
    ) == 2

    record = m.revoke_controller_transfer_approval(
        "a1", approver_id="g1", revocation_id="r1"
    )
    assert record.approval_id == "a1"
    assert m.controller_transfer_approval_is_revoked("a1")
    assert m.controller_transfer_quorum_count(
        "target",
        current_controller_id="org-owner",
        new_controller_id="org-new",
        transfer_evidence_id="ev-1",
        effective_epoch=1,
    ) == 1

    with pytest.raises(ValueError, match="threshold"):
        m.transfer_guardian_controller(
            "target",
            new_controller_id="org-new",
            authorized_by_controller_id="org-owner",
            transfer_id="t1",
            transfer_evidence_id="ev-1",
            effective_epoch=1,
        )


def test_only_original_approver_can_revoke():
    m = _memory()
    _approve(m, "g1", "a1")
    with pytest.raises(ValueError, match="original approver"):
        m.revoke_controller_transfer_approval(
            "a1", approver_id="g2", revocation_id="r1"
        )
    assert not m.controller_transfer_approval_is_revoked("a1")


def test_revocation_id_is_replay_protected():
    m = _memory()
    _approve(m, "g1", "a1")
    _approve(m, "g2", "a2")
    m.revoke_controller_transfer_approval(
        "a1", approver_id="g1", revocation_id="r1"
    )
    with pytest.raises(ValueError, match="revocation_id"):
        m.revoke_controller_transfer_approval(
            "a2", approver_id="g2", revocation_id="r1"
        )


def test_approval_cannot_be_revoked_twice():
    m = _memory()
    _approve(m, "g1", "a1")
    m.revoke_controller_transfer_approval(
        "a1", approver_id="g1", revocation_id="r1"
    )
    with pytest.raises(ValueError, match="already been revoked"):
        m.revoke_controller_transfer_approval(
            "a1", approver_id="g1", revocation_id="r2"
        )


def test_unknown_approval_cannot_be_revoked():
    m = _memory()
    with pytest.raises(ValueError, match="does not exist"):
        m.revoke_controller_transfer_approval(
            "missing", approver_id="g1", revocation_id="r1"
        )


def test_revocation_cannot_be_back_applied_after_effective_epoch():
    m = _memory()
    _approve(m, "g1", "a1")
    m.set_policy_epoch(2)
    with pytest.raises(ValueError, match="after effective epoch"):
        m.revoke_controller_transfer_approval(
            "a1", approver_id="g1", revocation_id="r1"
        )


def test_revocation_is_final_for_same_approver_transfer_tuple():
    m = _memory()
    _approve(m, "g1", "a1")
    m.revoke_controller_transfer_approval(
        "a1", approver_id="g1", revocation_id="r1"
    )
    with pytest.raises(ValueError, match="already approved this transfer tuple"):
        _approve(m, "g1", "a2")


def test_v125_behavior_remains_available_on_base_class():
    from memoria_resolutiva.controller_transfer_quorum_v125 import (
        ControllerTransferQuorumMemoryV125,
    )

    m = ControllerTransferQuorumMemoryV125()
    assert not hasattr(m, "revoke_controller_transfer_approval")
