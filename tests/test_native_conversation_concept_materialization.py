from __future__ import annotations

from memoria_resolutiva.native_concept_catalog import NativeConceptCatalog
from memoria_resolutiva.native_conversation import NativeConversationService


class _Lease:
    def __init__(self, *, changed: bool):
        self.changed = changed
        self.calls = []
        self.released = False

    def supports(self, name: str) -> bool:
        return name == "memoria_mobile_apply_concept_catalog_json"

    def call(self, name: str, payload: dict[str, object]):
        self.calls.append((name, payload))
        return 0, {
            "status": "OK",
            "changed": self.changed,
            "concept_count": payload["concept_count"],
            "fingerprint": payload["fingerprint"],
        }

    def release(self):
        self.released = True


class _Manager:
    def __init__(self, lease: _Lease):
        self.lease = lease

    def acquire(self, **_kwargs):
        return self.lease


def _catalog() -> NativeConceptCatalog:
    return NativeConceptCatalog(
        schema=1,
        namespace="semantic",
        concepts=(),
        fingerprint="sha256:" + "b" * 64,
    )


def test_native_conversation_materializes_catalog_through_owned_lease(tmp_path):
    lease = _Lease(changed=True)
    service = NativeConversationService(
        library_path=tmp_path / "unused.so",
        data_dir=tmp_path / "native",
        organization_id="org-a",
        runtime_manager=_Manager(lease),
    )
    assert service.materialize_concept_catalog(_catalog()) is True
    assert lease.calls[0][0] == "memoria_mobile_apply_concept_catalog_json"
    assert lease.calls[0][1]["concept_count"] == 0
    service.close()
    assert lease.released is True


def test_native_conversation_materialization_preserves_idempotent_noop(tmp_path):
    lease = _Lease(changed=False)
    service = NativeConversationService(
        library_path=tmp_path / "unused.so",
        data_dir=tmp_path / "native",
        organization_id="org-a",
        runtime_manager=_Manager(lease),
    )
    assert service.materialize_concept_catalog(_catalog()) is False
