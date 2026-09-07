from types import SimpleNamespace

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.semantic_activation_resolver import SemanticActivationConversationResolver


class EvidenceResolver:
    def __init__(self, core: EvidenceCore):
        self.evidence = SimpleNamespace(core=core)

    def resolve(self, *, query: str, session_id: str | None = None):
        return SimpleNamespace(status="UNRESOLVED", confidence=0.0, selected_context="")


def _semantic_core(namespace: str) -> EvidenceCore:
    core = EvidenceCore()
    core.observe_relation(
        "tipo_de",
        "semantic_role",
        "concept",
        evidence_id="meta-type-role",
        source_text="tipo_de expande conceitos",
        namespace=namespace,
    )
    core.observe_relation(
        "ONU",
        "tipo_de",
        "equipamento",
        evidence_id="onu-type-equipment",
        source_text="ONU é um tipo de equipamento",
        namespace=namespace,
    )
    core.observe_relation(
        "equipamento",
        "local",
        "rack-1",
        evidence_id="equipment-rack",
        source_text="O equipamento está no rack-1",
        namespace=namespace,
    )
    return core


def test_semantic_activation_proxy_expands_declared_concept_bridge():
    namespace = "offia:test"
    resolver = SemanticActivationConversationResolver(EvidenceResolver(_semantic_core(namespace)))

    payload = resolver.activate_relations(concept="ONU", session_id=namespace, depth=1, budget=1200)

    assert payload["status"] == "HIT"
    assert "ONU | tipo_de | equipamento" in payload["selected_context"]
    assert "equipamento | local | rack-1" in payload["selected_context"]


def test_product_chat_receives_semantically_expanded_facts_without_meta_relation():
    namespace = "offia:test"
    resolver = SemanticActivationConversationResolver(EvidenceResolver(_semantic_core(namespace)))
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    chat = ProductChatService(memory, MockLLMAdapter(), conversation_resolver=resolver)
    scope = MemoryScope("org-a", application_id="offia", user_id="user-1", agent_id=namespace)

    result = chat.run(scope=scope, message="ONU?", mode="memoria")
    context = "\n".join(result.context)

    assert "ONU | tipo_de | equipamento" in context
    assert "equipamento | local | rack-1" in context
    assert "semantic_role" not in context


def test_semantic_activation_keeps_two_concept_budget():
    namespace = "offia:test"
    core = _semantic_core(namespace)
    core.observe_relation(
        "subtipo_de",
        "semantic_role",
        "concept",
        evidence_id="meta-subtype-role",
        source_text="subtipo_de expande conceitos",
        namespace=namespace,
    )
    core.observe_relation(
        "equipamento",
        "subtipo_de",
        "ativo-de-rede",
        evidence_id="equipment-network-active",
        source_text="equipamento é subtipo de ativo-de-rede",
        namespace=namespace,
    )
    core.observe_relation(
        "ativo-de-rede",
        "segredo",
        "nao-deve-entrar",
        evidence_id="third-hop-secret",
        source_text="terceiro conceito",
        namespace=namespace,
    )
    resolver = SemanticActivationConversationResolver(EvidenceResolver(core), max_concepts=2)

    payload = resolver.activate_relations(concept="ONU", session_id=namespace, depth=1, budget=1200)

    assert payload["status"] == "HIT"
    assert "equipamento | local | rack-1" in payload["selected_context"]
    assert "nao-deve-entrar" not in payload["selected_context"]


def test_undeclared_relation_does_not_expand_semantically():
    namespace = "offia:test"
    core = EvidenceCore()
    core.observe_relation(
        "ONU",
        "related_to",
        "equipamento",
        evidence_id="weak-link",
        source_text="relação não declarada",
        namespace=namespace,
    )
    core.observe_relation(
        "equipamento",
        "local",
        "rack-9",
        evidence_id="equipment-rack-9",
        source_text="equipamento no rack-9",
        namespace=namespace,
    )
    resolver = SemanticActivationConversationResolver(EvidenceResolver(core))

    payload = resolver.activate_relations(concept="ONU", session_id=namespace, depth=1, budget=1200)

    assert payload["status"] == "HIT"
    assert "ONU | related_to | equipamento" in payload["selected_context"]
    assert "equipamento | local | rack-9" not in payload["selected_context"]
