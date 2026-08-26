import pytest

from memoria_resolutiva.key_compromise_recovery_v121 import KeyCompromiseRecoveryMemoryV121


def _memory():
    m = KeyCompromiseRecoveryMemoryV121()
    m.add_trusted_issuer("root")
    m.attest_authority("authority-a", issuer_id="root", attestation_id="att-1")
    m.bind_initial_authority_key(
        "authority-a", key_id="key-1", issuer_id="root", binding_id="bind-1"
    )
    return m


def test_compromised_key_is_quarantined_from_incident_epoch():
    m = _memory()
    m.report_key_compromise(
        "authority-a", key_id="key-1", issuer_id="root",
        compromise_id="cmp-1", compromised_at_epoch=3,
    )
    assert m.active_authority_key("authority-a", epoch=2) == "key-1"
    assert m.active_authority_key("authority-a", epoch=3) is None


def test_recovery_restores_logical_authority_with_new_key():
    m = _memory()
    m.report_key_compromise(
        "authority-a", key_id="key-1", issuer_id="root",
        compromise_id="cmp-1", compromised_at_epoch=3,
    )
    m.recover_authority_key(
        "authority-a", compromised_key_id="key-1", replacement_key_id="key-2",
        issuer_id="root", recovery_id="rec-1", recovery_evidence_id="evidence-1",
        effective_epoch=4,
    )
    assert m.active_authority_key("authority-a", epoch=3) is None
    assert m.active_authority_key("authority-a", epoch=4) == "key-2"
    assert m.authority_for_key("key-2") == "authority-a"


def test_compromised_key_cannot_authorize_normal_rotation():
    m = _memory()
    m.report_key_compromise(
        "authority-a", key_id="key-1", issuer_id="root",
        compromise_id="cmp-1", compromised_at_epoch=3,
    )
    with pytest.raises(ValueError):
        m.rotate_authority_key(
            "authority-a", previous_key_id="key-1", new_key_id="key-x",
            rotation_id="rot-x", continuity_evidence_id="cont-x", effective_epoch=3,
        )


def test_recovery_requires_original_attestation_issuer():
    m = _memory()
    m.add_trusted_issuer("other-root")
    m.report_key_compromise(
        "authority-a", key_id="key-1", issuer_id="root",
        compromise_id="cmp-1", compromised_at_epoch=1,
    )
    with pytest.raises(ValueError):
        m.recover_authority_key(
            "authority-a", compromised_key_id="key-1", replacement_key_id="key-2",
            issuer_id="other-root", recovery_id="rec-1",
            recovery_evidence_id="evidence-1", effective_epoch=2,
        )


def test_recovery_ids_and_evidence_are_replay_protected():
    m = _memory()
    m.report_key_compromise(
        "authority-a", key_id="key-1", issuer_id="root",
        compromise_id="cmp-1", compromised_at_epoch=1,
    )
    m.recover_authority_key(
        "authority-a", compromised_key_id="key-1", replacement_key_id="key-2",
        issuer_id="root", recovery_id="rec-1", recovery_evidence_id="evidence-1",
        effective_epoch=2,
    )
    with pytest.raises(ValueError):
        m.recover_authority_key(
            "authority-a", compromised_key_id="key-1", replacement_key_id="key-3",
            issuer_id="root", recovery_id="rec-1", recovery_evidence_id="evidence-2",
            effective_epoch=3,
        )


def test_normal_rotation_after_recovery_uses_recovered_key():
    m = _memory()
    m.report_key_compromise(
        "authority-a", key_id="key-1", issuer_id="root",
        compromise_id="cmp-1", compromised_at_epoch=2,
    )
    m.recover_authority_key(
        "authority-a", compromised_key_id="key-1", replacement_key_id="key-2",
        issuer_id="root", recovery_id="rec-1", recovery_evidence_id="evidence-1",
        effective_epoch=3,
    )
    m.rotate_authority_key(
        "authority-a", previous_key_id="key-2", new_key_id="key-3",
        rotation_id="rot-1", continuity_evidence_id="cont-1", effective_epoch=4,
    )
    assert m.active_authority_key("authority-a", epoch=3) == "key-2"
    assert m.active_authority_key("authority-a", epoch=4) == "key-3"


def test_v120_normal_rotation_semantics_remain_without_compromise():
    m = _memory()
    m.rotate_authority_key(
        "authority-a", previous_key_id="key-1", new_key_id="key-2",
        rotation_id="rot-1", continuity_evidence_id="cont-1", effective_epoch=2,
    )
    assert m.active_authority_key("authority-a", epoch=1) == "key-1"
    assert m.active_authority_key("authority-a", epoch=2) == "key-2"
