from __future__ import annotations

import pytest

from memoria_resolutiva.native_concept_catalog import (
    NATIVE_CONCEPT_APPLY_SYMBOL,
    NativeConceptCatalog,
    apply_native_concept_catalog,
)


class _Lease:
    def __init__(self, *, supported: bool = True, changed: bool = True):
        self.supported = supported
        self.changed = changed
        self.calls: list[tuple[str, dict[str, object]]] = []

    def supports(self, name: str) -> bool:
        return self.supported and name == NATIVE_CONCEPT_APPLY_SYMBOL

    def call(self, name: str, payload: dict[str, object]):
        self.calls.append((name, payload))
        return 0, {
            "status": "OK",
            "changed": self.changed,
            "concept_count": payload["concept_count"],
            "fingerprint": payload["fingerprint"],
        }


def _catalog() -> NativeConceptCatalog:
    return NativeConceptCatalog(
        schema=1,
        namespace="semantic",
        concepts=(
            {
                "concept_id": "concept:voltage",
                "namespace": "semantic",
                "canonical": "tensão",
                "sense_key": "eletrica",
                "aliases": ["ddp", "diferença de potencial"],
                "context_cues": ["circuito"],
            },
        ),
        fingerprint="sha256:" + "a" * 64,
    )


def test_wire_payload_uses_utf8_byte_lengths():
    payload = _catalog().wire_payload()
    row = payload["rows"][0]
    assert isinstance(row, str)
    assert "7:tensão" in row
    assert "22:diferença de potencial" in row
    assert payload["concept_count"] == 1


def test_apply_native_catalog_returns_changed_flag_and_exact_payload():
    lease = _Lease(changed=True)
    assert apply_native_concept_catalog(lease, _catalog()) is True
    assert lease.calls[0][0] == NATIVE_CONCEPT_APPLY_SYMBOL
    assert lease.calls[0][1]["fingerprint"] == _catalog().fingerprint


def test_apply_native_catalog_supports_idempotent_response():
    assert apply_native_concept_catalog(_Lease(changed=False), _catalog()) is False


def test_apply_native_catalog_rejects_runtime_without_additive_symbol():
    with pytest.raises(RuntimeError, match="does not support"):
        apply_native_concept_catalog(_Lease(supported=False), _catalog())
