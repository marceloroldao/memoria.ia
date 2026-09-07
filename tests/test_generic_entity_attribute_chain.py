from types import SimpleNamespace

from memoria_resolutiva.llm_adapter import LLMResponse, LLMUsage
from memoria_resolutiva.product_chat import ProductChatService, _rank_relational_context
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


class CaptureAdapter:
    provider_name = "capture"
    model_name = "capture-v1"

    def __init__(self):
        self.calls = []

    def generate(self, *, message: str, context):
        self.calls.append((message, tuple(context)))
        return LLMResponse(
            text="captured",
            provider=self.provider_name,
            model=self.model_name,
            usage=LLMUsage(input_tokens=1, output_tokens=1, estimated_cost_usd=0.0),
        )


class StructuralRouterIpResolver:
    def __init__(self):
        self.resolve_calls = []
        self.activation_calls = []

    def resolve(self, *, query: str, session_id: str | None = None):
        self.resolve_calls.append((query, session_id))
        return SimpleNamespace(
            status="UNRESOLVED",
            confidence=0.0,
            selected_context="",
            relations=(),
            provenance=(),
            memory_ids=(),
        )

    def activate_relations(
        self,
        *,
        concept: str,
        session_id: str | None,
        depth: int,
        budget: int,
        hop_decay: float,
        min_confidence: float,
    ):
        self.activation_calls.append((concept, session_id, depth, budget, hop_decay, min_confidence))
        if concept.casefold() != "roteador":
            return {"status": "UNRESOLVED", "confidence": 0.0, "selected_context": "", "relations": []}
        return {
            "status": "HIT",
            "confidence": 0.91,
            "selected_context": (
                "hAP-ac2 | is | roteador\n"
                "RB5009 | is | roteador\n"
                "roteador | is | RB5009\n"
                "RB5009 | ip | 192.168.88.1\n"
                "hAP-ac2 | ip | 192.168.10.1"
            ),
            "relations": [
                {"evidence_id": "hap-type", "subject_key": "hAP-ac2", "object_key": "roteador"},
                {"evidence_id": "rb-type", "subject_key": "RB5009", "object_key": "roteador"},
                {"evidence_id": "rb-owner", "subject_key": "roteador", "object_key": "RB5009"},
                {"evidence_id": "rb-ip", "subject_key": "RB5009", "object_key": "192.168.88.1"},
                {"evidence_id": "hap-ip", "subject_key": "hAP-ac2", "object_key": "192.168.10.1"},
            ],
        }


def _chat(resolver):
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    adapter = CaptureAdapter()
    chat = ProductChatService(memory, adapter, conversation_resolver=resolver)
    scope = MemoryScope("org-a", application_id="offia", user_id="user-1", agent_id="offia:test")
    return chat, adapter, scope


def test_router_ip_ranking_uses_same_generic_entity_attribute_rule():
    ranked = _rank_relational_context(
        "Qual é o IP do meu roteador?",
        (
            "hAP-ac2 | is | roteador\n"
            "RB5009 | is | roteador\n"
            "roteador | is | RB5009\n"
            "RB5009 | ip | 192.168.88.1\n"
            "hAP-ac2 | ip | 192.168.10.1"
        ),
    )
    lines = ranked.splitlines()
    assert set(lines[:3]) == {
        "RB5009 | is | roteador",
        "roteador | is | RB5009",
        "RB5009 | ip | 192.168.88.1",
    }
    assert lines.index("RB5009 | ip | 192.168.88.1") < lines.index("hAP-ac2 | ip | 192.168.10.1")
    assert len(lines) == 5


def test_router_ip_chain_reaches_llm_without_domain_specific_runtime_code():
    resolver = StructuralRouterIpResolver()
    chat, adapter, scope = _chat(resolver)
    message = "Qual é o IP do meu roteador?"
    result = chat.run(scope=scope, message=message, mode="memoria")

    assert result.metrics.memory_hits == 1
    assert resolver.activation_calls
    assert resolver.activation_calls[0][0] == "roteador"
    assert resolver.activation_calls[0][2] == 2
    research = result.context[0].splitlines()
    assert set(research[:3]) == {
        "RB5009 | is | roteador",
        "roteador | is | RB5009",
        "RB5009 | ip | 192.168.88.1",
    }
    assert research.index("RB5009 | ip | 192.168.88.1") < research.index("hAP-ac2 | ip | 192.168.10.1")
    assert adapter.calls == [(message, result.context)]
