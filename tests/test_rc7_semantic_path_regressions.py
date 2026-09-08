from types import SimpleNamespace

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.semantic_activation_resolver import SemanticActivationConversationResolver


class TrackingResolver:
    def __init__(self, core: EvidenceCore):
        self.evidence = SimpleNamespace(core=core)
        self.calls = []
        self.result = SimpleNamespace(status="HIT", confidence=0.91, selected_context="direct-context")

    def resolve(self, *, query: str, session_id: str | None = None):
        self.calls.append((query, session_id))
        return self.result


def _core(namespace: str, reverse: bool = False) -> EvidenceCore:
    core = EvidenceCore()
    rows = [
        ("tipo_de", "semantic_role", "concept", "meta-type-role"),
        ("ONU", "tipo_de", "equipamento", "onu-type-equipment"),
        ("equipamento", "local", "rack-1", "equipment-rack"),
        ("equipamento", "fabricante", "vendor-a", "equipment-vendor"),
    ]
    if reverse:
        rows = list(reversed(rows))
    for subject, predicate, object_, evidence_id in rows:
        core.observe_relation(
            subject,
            predicate,
            object_,
            evidence_id=evidence_id,
            source_text=f"{subject} {predicate} {object_}",
            namespace=namespace,
        )
    return core


def test_rc7_proxy_delegates_direct_resolution_without_mutation():
    namespace = "offia:rc7"
    base = TrackingResolver(_core(namespace))
    proxy = SemanticActivationConversationResolver(base)

    result = proxy.resolve(query="consulta direta", session_id=namespace)

    assert result is base.result
    assert base.calls == [("consulta direta", namespace)]


def test_rc7_semantic_context_is_deterministic_under_insertion_order_variation():
    namespace = "offia:rc7"
    a = SemanticActivationConversationResolver(TrackingResolver(_core(namespace, reverse=False)))
    b = SemanticActivationConversationResolver(TrackingResolver(_core(namespace, reverse=True)))

    pa = a.activate_relations(concept="ONU", session_id=namespace, depth=1, budget=1200)
    pb = b.activate_relations(concept="ONU", session_id=namespace, depth=1, budget=1200)

    assert pa["status"] == "HIT"
    assert pb["status"] == "HIT"
    assert pa["selected_context"] == pb["selected_context"]


def test_rc7_context_budget_preserves_complete_relation_lines():
    namespace = "offia:rc7"
    proxy = SemanticActivationConversationResolver(TrackingResolver(_core(namespace)))

    payload = proxy.activate_relations(concept="ONU", session_id=namespace, depth=1, budget=34)

    assert len(payload["selected_context"]) <= 34
    for line in payload["selected_context"].splitlines():
        assert line.count(" | ") == 2
        subject, predicate, object_ = line.split(" | ")
        assert subject.strip()
        assert predicate.strip()
        assert object_.strip()


def test_rc7_duplicate_semantic_evidence_is_not_duplicated_in_prompt_context():
    namespace = "offia:rc7"
    core = _core(namespace)
    core.observe_relation(
        "equipamento",
        "local",
        "rack-1",
        evidence_id="equipment-rack-duplicate",
        source_text="duplicate evidence",
        namespace=namespace,
    )
    proxy = SemanticActivationConversationResolver(TrackingResolver(core))

    payload = proxy.activate_relations(concept="ONU", session_id=namespace, depth=1, budget=1200)

    lines = payload["selected_context"].splitlines()
    assert lines.count("equipamento | local | rack-1") == 1


def test_rc7_semantic_role_metadata_stays_out_of_context():
    namespace = "offia:rc7"
    proxy = SemanticActivationConversationResolver(TrackingResolver(_core(namespace)))

    payload = proxy.activate_relations(concept="ONU", session_id=namespace, depth=1, budget=1200)

    assert "semantic_role" not in payload["selected_context"]
    assert "ONU | tipo_de | equipamento" in payload["selected_context"]
