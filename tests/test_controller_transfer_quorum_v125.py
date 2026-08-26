import pytest

from memoria_resolutiva.controller_transfer_quorum_v125 import ControllerTransferQuorumMemoryV125


def _memory():
    m = ControllerTransferQuorumMemoryV125()
    m.bind_guardian_controller("target", controller_id="org-owner")
    m.bind_guardian_controller("g1", controller_id="org-a")
    m.bind_guardian_controller("g2", controller_id="org-b")
    m.bind_guardian_controller("g3", controller_id="org-a")
    return m


def _approve(m, approver, approval_id, *, evidence="ev-1", new="org-new", epoch=0):
    return m.approve_controller_transfer(
        "target", current_controller_id="org-owner", new_controller_id=new,
        approver_id=approver, approval_id=approval_id,
        transfer_evidence_id=evidence, effective_epoch=epoch,
    )


def test_transfer_requires_configured_quorum():
    m = _memory()
    with pytest.raises(ValueError, match="policy is not configured"):
        m.transfer_guardian_controller(
            "target", new_controller_id="org-new", authorized_by_controller_id="org-owner",
            transfer_id="t1", transfer_evidence_id="ev-1", effective_epoch=0,
        )


def test_same_controller_approvals_count_once():
    m = _memory()
    m.configure_controller_transfer_quorum("target", approver_ids=["g1", "g2", "g3"], threshold=2)
    _approve(m, "g1", "a1")
    _approve(m, "g3", "a2")
    assert m.controller_transfer_quorum_count(
        "target", current_controller_id="org-owner", new_controller_id="org-new",
        transfer_evidence_id="ev-1", effective_epoch=0,
    ) == 1
    with pytest.raises(ValueError, match="threshold"):
        m.transfer_guardian_controller(
            "target", new_controller_id="org-new", authorized_by_controller_id="org-owner",
            transfer_id="t1", transfer_evidence_id="ev-1", effective_epoch=0,
        )


def test_independent_controllers_authorize_transfer():
    m = _memory()
    m.configure_controller_transfer_quorum("target", approver_ids=["g1", "g2"], threshold=2)
    _approve(m, "g1", "a1")
    _approve(m, "g2", "a2")
    m.transfer_guardian_controller(
        "target", new_controller_id="org-new", authorized_by_controller_id="org-owner",
        transfer_id="t1", transfer_evidence_id="ev-1", effective_epoch=0,
    )
    assert m.guardian_controller("target") == "org-new"


def test_threshold_cannot_exceed_independent_approver_controllers():
    m = _memory()
    with pytest.raises(ValueError, match="independent approver controllers"):
        m.configure_controller_transfer_quorum("target", approver_ids=["g1", "g3"], threshold=2)


def test_approvals_are_bound_to_exact_transfer_tuple():
    m = _memory()
    m.configure_controller_transfer_quorum("target", approver_ids=["g1", "g2"], threshold=2)
    _approve(m, "g1", "a1", evidence="ev-1", new="org-new")
    _approve(m, "g2", "a2", evidence="ev-2", new="org-other")
    assert m.controller_transfer_quorum_count(
        "target", current_controller_id="org-owner", new_controller_id="org-new",
        transfer_evidence_id="ev-1", effective_epoch=0,
    ) == 1


def test_transfer_approval_id_is_replay_protected():
    m = _memory()
    m.configure_controller_transfer_quorum("target", approver_ids=["g1"], threshold=1)
    _approve(m, "g1", "a1")
    with pytest.raises(ValueError, match="already been applied"):
        _approve(m, "g1", "a1")


def test_recovery_and_transfer_policies_are_separate():
    m = _memory()
    m.configure_controller_transfer_quorum("target", approver_ids=["g1", "g2"], threshold=2)
    assert "target" in m._transfer_policy
    assert "target" not in m._recovery_policy


def test_v124_direct_transfer_remains_available_on_base_class():
    from memoria_resolutiva.controller_transfer_v124 import ControllerTransferMemoryV124

    m = ControllerTransferMemoryV124()
    m.bind_guardian_controller("target", controller_id="org-owner")
    m.transfer_guardian_controller(
        "target", new_controller_id="org-new", authorized_by_controller_id="org-owner",
        transfer_id="t1", transfer_evidence_id="ev-1", effective_epoch=0,
    )
    assert m.guardian_controller("target") == "org-new"
