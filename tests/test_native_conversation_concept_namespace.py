from __future__ import annotations

from memoria_resolutiva.native_conversation import NativeConversationService


class _Lease:
    def __init__(self):
        self.calls = []

    def call(self, name: str, payload: dict[str, object]):
        self.calls.append((name, payload))
        return 2, {"status": "UNRESOLVED"}

    def release(self):
        pass


class _Manager:
    def __init__(self):
        self.lease = _Lease()

    def acquire(self, **_kwargs):
        return self.lease


def test_native_resolve_transports_concept_namespace_separately(tmp_path):
    manager = _Manager()
    service = NativeConversationService(
        library_path=tmp_path / "unused.so",
        data_dir=tmp_path / "native",
        organization_id="org-a",
        concept_namespace="semantic",
        runtime_manager=manager,
    )
    result = service.resolve(query="ddp", session_id="session-a")
    assert result.status == "UNRESOLVED"
    assert manager.lease.calls == [
        (
            "memoria_mobile_resolve_context_json",
            {"query": "ddp", "namespace": "session-a", "concept_namespace": "semantic"},
        )
    ]
