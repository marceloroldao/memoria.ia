from types import SimpleNamespace

from memoria_resolutiva.native_resolve import NativeResolveService
from memoria_resolutiva.product_identity import MemoryScope


class Resolver:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def resolve(self, *, query, session_id=None):
        self.calls.append((query, session_id))
        return self.result


def scope():
    return MemoryScope("org-a", application_id="web", agent_id="session-1")


def test_native_resolve_returns_persisted_context_without_external_call():
    resolver = Resolver(SimpleNamespace(
        status="HIT",
        confidence=0.94,
        selected_context="camisa | cor | preta",
    ))
    result = NativeResolveService(resolver).resolve(
        scope=scope(),
        message="Qual era a cor da minha camisa?",
    )
    assert result.status == "RESOLVED"
    assert result.text == "camisa | cor | preta"
    assert result.confidence == 0.94
    assert result.external_calls == 0
    assert resolver.calls == [("Qual era a cor da minha camisa?", "session-1")]


def test_native_resolve_refuses_weak_evidence_instead_of_generating():
    resolver = Resolver(SimpleNamespace(
        status="HIT",
        confidence=0.41,
        selected_context="camisa | cor | talvez preta",
    ))
    result = NativeResolveService(resolver).resolve(scope=scope(), message="Qual a cor?")
    assert result.status == "UNRESOLVED"
    assert result.text is None
    assert result.external_calls == 0


def test_native_resolve_refuses_missing_evidence():
    resolver = Resolver(SimpleNamespace(status="UNRESOLVED", confidence=0.0, selected_context=""))
    result = NativeResolveService(resolver).resolve(scope=scope(), message="Onde está o objeto?")
    assert result.status == "UNRESOLVED"
    assert result.context == ()
    assert result.external_calls == 0
