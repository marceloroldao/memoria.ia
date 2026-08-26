import pytest

from memoria_resolutiva.authority_attestation_v118 import AuthorityAttestationMemoryV118


def _two_authority_memory():
    mem = AuthorityAttestationMemoryV118()
    mem.observe("A fonte Delta alimenta o controlador.", provenance="p1", origin="o1", confidence=0.9)
    mem.observe("A fonte Delta alimenta o controlador.", provenance="p2", origin="o2", confidence=0.9)
    mem.register_origin_authority("o1", "a1")
    mem.register_origin_authority("o2", "a2")
    return mem


def test_unverified_authorities_fail_verified_gate():
    mem = _two_authority_memory()
    assert not mem.infer_path(
        "Delta", "controlador", min_independent_authorities=2,
        require_verified_authorities=True, min_verified_authorities=2
    ).inferred


def test_trusted_issuer_can_attest_authorities():
    mem = _two_authority_memory()
    mem.add_trusted_issuer("root")
    mem.attest_authority("a1", issuer_id="root", attestation_id="att-1")
    mem.attest_authority("a2", issuer_id="root", attestation_id="att-2")
    assert mem.infer_path(
        "Delta", "controlador", min_independent_authorities=2,
        require_verified_authorities=True, min_verified_authorities=2
    ).inferred


def test_untrusted_issuer_cannot_create_verification():
    mem = _two_authority_memory()
    with pytest.raises(ValueError):
        mem.attest_authority("a1", issuer_id="unknown", attestation_id="att-1")
    assert not mem.is_authority_verified("a1")


def test_duplicate_attestation_id_is_rejected():
    mem = _two_authority_memory()
    mem.add_trusted_issuer("root")
    mem.attest_authority("a1", issuer_id="root", attestation_id="att-1")
    with pytest.raises(ValueError):
        mem.attest_authority("a2", issuer_id="root", attestation_id="att-1")


def test_authority_attestation_is_immutable():
    mem = _two_authority_memory()
    mem.add_trusted_issuer("root1")
    mem.add_trusted_issuer("root2")
    mem.attest_authority("a1", issuer_id="root1", attestation_id="att-1")
    with pytest.raises(ValueError):
        mem.attest_authority("a1", issuer_id="root2", attestation_id="att-2")


def test_verification_does_not_replace_authority_diversity():
    mem = AuthorityAttestationMemoryV118()
    mem.observe("A fonte Delta alimenta o controlador.", provenance="p1", origin="o1", confidence=0.9)
    mem.observe("A fonte Delta alimenta o controlador.", provenance="p2", origin="o2", confidence=0.9)
    mem.register_origin_authority("o1", "a1")
    mem.register_origin_authority("o2", "a1")
    mem.add_trusted_issuer("root")
    mem.attest_authority("a1", issuer_id="root", attestation_id="att-1")
    assert not mem.infer_path(
        "Delta", "controlador", min_independent_authorities=2,
        require_verified_authorities=True, min_verified_authorities=1
    ).inferred


def test_v117_semantics_remain_when_verification_not_required():
    mem = _two_authority_memory()
    assert mem.infer_path(
        "Delta", "controlador", min_independent_origins=2, min_independent_authorities=2
    ).inferred
