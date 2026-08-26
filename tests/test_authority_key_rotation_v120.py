import pytest

from memoria_resolutiva.authority_key_rotation_v120 import AuthorityKeyRotationMemoryV120


def _memory():
    m = AuthorityKeyRotationMemoryV120()
    m.add_trusted_issuer("root")
    m.attest_authority("authority-a", issuer_id="root", attestation_id="att-1")
    return m


def test_initial_key_requires_attested_authority_and_matching_issuer():
    m = AuthorityKeyRotationMemoryV120()
    m.add_trusted_issuer("root")
    with pytest.raises(ValueError):
        m.bind_initial_authority_key(
            "authority-a", key_id="key-1", issuer_id="root", binding_id="bind-1"
        )
    m.attest_authority("authority-a", issuer_id="root", attestation_id="att-1")
    with pytest.raises(ValueError):
        m.bind_initial_authority_key(
            "authority-a", key_id="key-1", issuer_id="other", binding_id="bind-1"
        )


def test_rotation_preserves_logical_authority_and_historical_key():
    m = _memory()
    m.bind_initial_authority_key(
        "authority-a", key_id="key-1", issuer_id="root", binding_id="bind-1"
    )
    m.rotate_authority_key(
        "authority-a",
        previous_key_id="key-1",
        new_key_id="key-2",
        rotation_id="rot-1",
        continuity_evidence_id="proof-1",
        effective_epoch=3,
    )
    assert m.active_authority_key("authority-a", epoch=2) == "key-1"
    assert m.active_authority_key("authority-a", epoch=3) == "key-2"
    assert m.authority_for_key("key-1") == "authority-a"
    assert m.authority_for_key("key-2") == "authority-a"


def test_new_key_never_becomes_active_without_rotation():
    m = _memory()
    m.bind_initial_authority_key(
        "authority-a", key_id="key-1", issuer_id="root", binding_id="bind-1"
    )
    assert not m.is_authority_key_active("authority-a", "key-2")
    assert m.authority_for_key("key-2") is None


def test_rotation_rejects_non_active_predecessor():
    m = _memory()
    m.bind_initial_authority_key(
        "authority-a", key_id="key-1", issuer_id="root", binding_id="bind-1"
    )
    with pytest.raises(ValueError):
        m.rotate_authority_key(
            "authority-a",
            previous_key_id="fake-key",
            new_key_id="key-2",
            rotation_id="rot-1",
            continuity_evidence_id="proof-1",
        )


def test_rotation_and_continuity_ids_are_replay_protected():
    m = _memory()
    m.bind_initial_authority_key(
        "authority-a", key_id="key-1", issuer_id="root", binding_id="bind-1"
    )
    m.rotate_authority_key(
        "authority-a",
        previous_key_id="key-1",
        new_key_id="key-2",
        rotation_id="rot-1",
        continuity_evidence_id="proof-1",
    )
    with pytest.raises(ValueError):
        m.rotate_authority_key(
            "authority-a",
            previous_key_id="key-2",
            new_key_id="key-3",
            rotation_id="rot-1",
            continuity_evidence_id="proof-2",
        )
    with pytest.raises(ValueError):
        m.rotate_authority_key(
            "authority-a",
            previous_key_id="key-2",
            new_key_id="key-3",
            rotation_id="rot-2",
            continuity_evidence_id="proof-1",
        )


def test_key_cannot_be_shared_across_authorities():
    m = _memory()
    m.attest_authority("authority-b", issuer_id="root", attestation_id="att-2")
    m.bind_initial_authority_key(
        "authority-a", key_id="shared-key", issuer_id="root", binding_id="bind-1"
    )
    with pytest.raises(ValueError):
        m.bind_initial_authority_key(
            "authority-b", key_id="shared-key", issuer_id="root", binding_id="bind-2"
        )


def test_revoked_authority_key_is_not_active_for_current_policy():
    m = _memory()
    m.bind_initial_authority_key(
        "authority-a", key_id="key-1", issuer_id="root", binding_id="bind-1"
    )
    m.set_policy_epoch(4)
    m.revoke_authority(
        "authority-a", issuer_id="root", revocation_id="rev-1", revoked_at_epoch=4
    )
    assert not m.is_authority_key_active("authority-a", "key-1")
    assert m.is_authority_key_active("authority-a", "key-1", epoch=3)
