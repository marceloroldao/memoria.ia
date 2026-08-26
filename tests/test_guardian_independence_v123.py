import pytest

from memoria_resolutiva.guardian_independence_v123 import GuardianIndependenceMemoryV123


def _memory():
    m = GuardianIndependenceMemoryV123()
    m.add_trusted_issuer("root")
    m.attest_authority("authority", issuer_id="root", attestation_id="att-1")
    m.bind_initial_authority_key(
        "authority", key_id="key-1", issuer_id="root", binding_id="bind-1"
    )
    m.report_key_compromise(
        "authority", key_id="key-1", issuer_id="root", compromise_id="comp-1"
    )
    return m


def _approve(m, guardian, approval_id, replacement="key-2", evidence="ev-1"):
    return m.approve_recovery(
        "authority",
        compromised_key_id="key-1",
        replacement_key_id=replacement,
        approver_id=guardian,
        approval_id=approval_id,
        recovery_evidence_id=evidence,
    )


def test_same_controller_counts_once():
    m = _memory()
    m.bind_guardian_controller("g1", controller_id="org-a")
    m.bind_guardian_controller("g2", controller_id="org-a")
    m.bind_guardian_controller("g3", controller_id="org-b")
    m.configure_recovery_quorum("authority", approver_ids=["g1", "g2", "g3"], threshold=2)
    _approve(m, "g1", "a1")
    _approve(m, "g2", "a2")
    assert m.recovery_quorum_count(
        "authority", compromised_key_id="key-1", replacement_key_id="key-2", recovery_evidence_id="ev-1"
    ) == 1
    with pytest.raises(ValueError, match="threshold"):
        m.recover_authority_key(
            "authority", compromised_key_id="key-1", replacement_key_id="key-2",
            issuer_id="root", recovery_id="r1", recovery_evidence_id="ev-1"
        )
    _approve(m, "g3", "a3")
    m.recover_authority_key(
        "authority", compromised_key_id="key-1", replacement_key_id="key-2",
        issuer_id="root", recovery_id="r1", recovery_evidence_id="ev-1"
    )
    assert m.active_authority_key("authority") == "key-2"


def test_threshold_cannot_exceed_independent_controllers():
    m = _memory()
    m.bind_guardian_controller("g1", controller_id="org-a")
    m.bind_guardian_controller("g2", controller_id="org-a")
    with pytest.raises(ValueError, match="independent controllers"):
        m.configure_recovery_quorum("authority", approver_ids=["g1", "g2"], threshold=2)


def test_every_guardian_requires_controller_binding():
    m = _memory()
    m.bind_guardian_controller("g1", controller_id="org-a")
    with pytest.raises(ValueError, match="controller binding"):
        m.configure_recovery_quorum("authority", approver_ids=["g1", "g2"], threshold=1)


def test_controller_binding_is_immutable():
    m = _memory()
    m.bind_guardian_controller("g1", controller_id="org-a")
    m.bind_guardian_controller("g1", controller_id="org-a")
    with pytest.raises(ValueError, match="immutable"):
        m.bind_guardian_controller("g1", controller_id="org-b")


def test_different_controllers_satisfy_quorum():
    m = _memory()
    m.bind_guardian_controller("g1", controller_id="org-a")
    m.bind_guardian_controller("g2", controller_id="org-b")
    m.configure_recovery_quorum("authority", approver_ids=["g1", "g2"], threshold=2)
    _approve(m, "g1", "a1")
    _approve(m, "g2", "a2")
    assert m.recovery_quorum_count(
        "authority", compromised_key_id="key-1", replacement_key_id="key-2", recovery_evidence_id="ev-1"
    ) == 2


def test_controller_independence_does_not_mix_recovery_tuples():
    m = _memory()
    m.bind_guardian_controller("g1", controller_id="org-a")
    m.bind_guardian_controller("g2", controller_id="org-b")
    m.configure_recovery_quorum("authority", approver_ids=["g1", "g2"], threshold=2)
    _approve(m, "g1", "a1", replacement="key-2", evidence="ev-1")
    _approve(m, "g2", "a2", replacement="key-3", evidence="ev-2")
    assert m.recovery_quorum_count(
        "authority", compromised_key_id="key-1", replacement_key_id="key-2", recovery_evidence_id="ev-1"
    ) == 1


def test_v122_raw_guardian_quorum_remains_available_on_base_class():
    from memoria_resolutiva.recovery_quorum_v122 import RecoveryQuorumMemoryV122

    m = RecoveryQuorumMemoryV122()
    m.add_trusted_issuer("root")
    m.attest_authority("authority", issuer_id="root", attestation_id="att-1")
    m.bind_initial_authority_key("authority", key_id="key-1", issuer_id="root", binding_id="bind-1")
    m.configure_recovery_quorum("authority", approver_ids=["g1", "g2"], threshold=2)
