import pytest

from memoria_resolutiva.attestation_lifecycle_v119 import AttestationLifecycleMemoryV119


def _memory():
    m = AttestationLifecycleMemoryV119()
    m.add_trusted_issuer("root")
    return m


def test_attestation_validity_window_is_epoch_bound():
    m = _memory()
    m.attest_authority(
        "authority-a",
        issuer_id="root",
        attestation_id="att-1",
        valid_from_epoch=2,
        expires_at_epoch=5,
    )
    assert not m.is_authority_verified("authority-a", epoch=1)
    assert m.is_authority_verified("authority-a", epoch=2)
    assert m.is_authority_verified("authority-a", epoch=4)
    assert not m.is_authority_verified("authority-a", epoch=5)


def test_policy_epoch_is_monotonic_and_drives_default_verification():
    m = _memory()
    m.attest_authority(
        "authority-a",
        issuer_id="root",
        attestation_id="att-1",
        expires_at_epoch=3,
    )
    assert m.is_authority_verified("authority-a")
    m.set_policy_epoch(3)
    assert not m.is_authority_verified("authority-a")
    with pytest.raises(ValueError):
        m.set_policy_epoch(2)


def test_only_original_issuer_can_revoke():
    m = _memory()
    m.add_trusted_issuer("other-root")
    m.attest_authority("authority-a", issuer_id="root", attestation_id="att-1")
    with pytest.raises(ValueError):
        m.revoke_authority(
            "authority-a",
            issuer_id="other-root",
            revocation_id="rev-1",
        )
    assert m.is_authority_verified("authority-a")


def test_revocation_is_append_only_and_historical_queries_still_work():
    m = _memory()
    m.attest_authority("authority-a", issuer_id="root", attestation_id="att-1")
    m.set_policy_epoch(4)
    m.revoke_authority(
        "authority-a",
        issuer_id="root",
        revocation_id="rev-1",
        revoked_at_epoch=4,
    )
    assert not m.is_authority_verified("authority-a")
    assert m.is_authority_verified("authority-a", epoch=3)
    assert not m.is_authority_verified("authority-a", epoch=4)
    assert len(m.authority_revocations()) == 1


def test_duplicate_revocation_id_is_rejected():
    m = _memory()
    m.attest_authority("authority-a", issuer_id="root", attestation_id="att-1")
    m.revoke_authority("authority-a", issuer_id="root", revocation_id="rev-1")
    with pytest.raises(ValueError):
        m.revoke_authority("authority-a", issuer_id="root", revocation_id="rev-1")


def test_expired_authority_cannot_satisfy_verified_authority_gate():
    m = _memory()
    m.register_origin_authority("origin-a", "authority-a")
    m.attest_authority(
        "authority-a",
        issuer_id="root",
        attestation_id="att-1",
        expires_at_epoch=2,
    )
    m.observe(
        "Alpha powers Beta",
        provenance="sensor-a",
        origin="origin-a",
        confidence=0.9,
    )
    assert m.infer_path(
        "Alpha",
        "Beta",
        require_verified_authorities=True,
        authority_epoch=1,
    ).inferred
    assert not m.infer_path(
        "Alpha",
        "Beta",
        require_verified_authorities=True,
        authority_epoch=2,
    ).inferred


def test_v118_behavior_is_preserved_when_lifecycle_has_no_expiry_or_revocation():
    m = _memory()
    m.register_origin_authority("origin-a", "authority-a")
    m.attest_authority("authority-a", issuer_id="root", attestation_id="att-1")
    m.observe(
        "Alpha powers Beta",
        provenance="sensor-a",
        origin="origin-a",
        confidence=0.9,
    )
    result = m.infer_path(
        "Alpha",
        "Beta",
        require_verified_authorities=True,
        min_verified_authorities=1,
    )
    assert result.inferred
