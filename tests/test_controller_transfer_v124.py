import pytest

from memoria_resolutiva.controller_transfer_v124 import ControllerTransferMemoryV124


def _memory():
    m = ControllerTransferMemoryV124()
    m.add_trusted_issuer("root")
    m.attest_authority("authority", issuer_id="root", attestation_id="att-1")
    m.bind_initial_authority_key(
        "authority", key_id="key-1", issuer_id="root", binding_id="bind-1"
    )
    m.report_key_compromise(
        "authority", key_id="key-1", issuer_id="root", compromise_id="comp-1"
    )
    return m


def _approve(m, guardian, approval_id, evidence="ev-1"):
    return m.approve_recovery(
        "authority",
        compromised_key_id="key-1",
        replacement_key_id="key-2",
        approver_id=guardian,
        approval_id=approval_id,
        recovery_evidence_id=evidence,
    )


def test_controller_transfer_is_temporal_and_historical():
    m = _memory()
    m.bind_guardian_controller("g1", controller_id="org-a")
    assert m.guardian_controller_at("g1", epoch=0) == "org-a"
    m.set_policy_epoch(2)
    m.transfer_guardian_controller(
        "g1", new_controller_id="org-b", authorized_by_controller_id="org-a",
        transfer_id="t1", transfer_evidence_id="tev-1"
    )
    assert m.guardian_controller_at("g1", epoch=1) == "org-a"
    assert m.guardian_controller_at("g1", epoch=2) == "org-b"
    assert m.guardian_controller("g1") == "org-b"


def test_transfer_requires_current_controller_authorization():
    m = _memory()
    m.bind_guardian_controller("g1", controller_id="org-a")
    m.set_policy_epoch(1)
    with pytest.raises(ValueError, match="current controller"):
        m.transfer_guardian_controller(
            "g1", new_controller_id="org-b", authorized_by_controller_id="org-x",
            transfer_id="t1", transfer_evidence_id="tev-1"
        )
    assert m.guardian_controller("g1") == "org-a"


def test_transfer_cannot_be_backdated():
    m = _memory()
    m.bind_guardian_controller("g1", controller_id="org-a")
    m.set_policy_epoch(3)
    with pytest.raises(ValueError, match="backdated"):
        m.transfer_guardian_controller(
            "g1", new_controller_id="org-b", authorized_by_controller_id="org-a",
            transfer_id="t1", transfer_evidence_id="tev-1", effective_epoch=2
        )


def test_transfer_ids_and_evidence_are_replay_protected():
    m = _memory()
    m.bind_guardian_controller("g1", controller_id="org-a")
    m.bind_guardian_controller("g2", controller_id="org-c")
    m.set_policy_epoch(1)
    m.transfer_guardian_controller(
        "g1", new_controller_id="org-b", authorized_by_controller_id="org-a",
        transfer_id="t1", transfer_evidence_id="tev-1"
    )
    m.set_policy_epoch(2)
    with pytest.raises(ValueError, match="transfer_id"):
        m.transfer_guardian_controller(
            "g2", new_controller_id="org-d", authorized_by_controller_id="org-c",
            transfer_id="t1", transfer_evidence_id="tev-2"
        )
    with pytest.raises(ValueError, match="transfer_evidence_id"):
        m.transfer_guardian_controller(
            "g2", new_controller_id="org-d", authorized_by_controller_id="org-c",
            transfer_id="t2", transfer_evidence_id="tev-1"
        )


def test_quorum_uses_controller_at_approval_epoch():
    m = _memory()
    m.bind_guardian_controller("g1", controller_id="org-a")
    m.bind_guardian_controller("g2", controller_id="org-b")
    m.configure_recovery_quorum("authority", approver_ids=["g1", "g2"], threshold=2)
    _approve(m, "g1", "a1")
    m.set_policy_epoch(1)
    m.transfer_guardian_controller(
        "g1", new_controller_id="org-b", authorized_by_controller_id="org-a",
        transfer_id="t1", transfer_evidence_id="tev-1"
    )
    _approve(m, "g2", "a2")
    assert m.guardian_controller("g1") == "org-b"
    assert m.recovery_quorum_count(
        "authority", compromised_key_id="key-1", replacement_key_id="key-2",
        recovery_evidence_id="ev-1"
    ) == 2


def test_new_policy_uses_current_controller_state():
    m = _memory()
    m.bind_guardian_controller("g1", controller_id="org-a")
    m.bind_guardian_controller("g2", controller_id="org-b")
    m.set_policy_epoch(1)
    m.transfer_guardian_controller(
        "g1", new_controller_id="org-b", authorized_by_controller_id="org-a",
        transfer_id="t1", transfer_evidence_id="tev-1"
    )
    with pytest.raises(ValueError, match="independent controllers"):
        m.configure_recovery_quorum("authority", approver_ids=["g1", "g2"], threshold=2)


def test_v123_immutable_binding_semantics_remain_on_base_class():
    from memoria_resolutiva.guardian_independence_v123 import GuardianIndependenceMemoryV123

    m = GuardianIndependenceMemoryV123()
    m.bind_guardian_controller("g1", controller_id="org-a")
    with pytest.raises(ValueError, match="immutable"):
        m.bind_guardian_controller("g1", controller_id="org-b")
