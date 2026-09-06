from types import SimpleNamespace

import pytest

from memoria_resolutiva.llm_adapter import LLMResponse, LLMUsage
from memoria_resolutiva.product_chat import ProductChatService, _relation_probe_queries
from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


class RelationalCatResolver:
    def __init__(self):
        self.calls = []

    def resolve(self, *, query: str, session_id: str | None = None):
        self.calls.append((query, session_id))
        return SimpleNamespace(
            status="HIT",
            confidence=0.99,
            selected_context=(
                "Alt é um gato do usuário.\n"
                "Vivi é um gato.\n"
                "Lay é um gato."
            ),
            relations=(
                {"subject": "Alt", "predicate": "is_a", "object": "gato", "confidence": 0.99},
                {"subject": "Alt", "predicate": "belongs_to", "object": "usuario", "confidence": 0.99},
                {"subject": "Vivi", "predicate": "is_a", "object": "gato", "confidence": 0.98},
                {"subject": "Lay", "predicate": "is_a", "object": "gato", "confidence": 0.98},
            ),
            provenance=(
                {"memory_id": "alt-type", "source_type": "user_assertion"},
                {"memory_id": "alt-owner", "source_type": "user_assertion"},
                {"memory_id": "vivi-type", "source_type": "user_assertion"},
                {"memory_id": "lay-type", "source_type": "user_assertion"},
            ),
            memory_ids=("alt-type", "alt-owner", "vivi-type", "lay-type"),
        )


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


class MissThenProbeHitResolver:
    def __init__(self, probe: str, selected_context: str, confidence: float = 0.9):
        self.probe = probe
        self.selected_context = selected_context
        self.confidence = confidence
        self.calls = []

    def resolve(self, *, query: str, session_id: str | None = None):
        self.calls.append((query, session_id))
        if query != self.probe:
            return SimpleNamespace(status="UNRESOLVED", confidence=0.0, selected_context="", relations=(), provenance=(), memory_ids=())
        return SimpleNamespace(
            status="HIT",
            confidence=self.confidence,
            selected_context=self.selected_context,
            relations=(),
            provenance=(),
            memory_ids=("probe-hit",),
        )


class TwoHopResolver:
    def __init__(self, *, first_confidence: float = 0.9, second_context: str = "PPPoE | upstream | OLT"):
        self.first_confidence = first_confidence
        self.second_context = second_context
        self.calls = []

    def resolve(self, *, query: str, session_id: str | None = None):
        self.calls.append((query, session_id))
        if query == "A internet caiu":
            return SimpleNamespace(status="UNRESOLVED", confidence=0.0, selected_context="", relations=(), provenance=(), memory_ids=())
        if query == "O que está relacionado a internet?":
            return SimpleNamespace(
                status="HIT",
                confidence=self.first_confidence,
                selected_context="internet PPPoE",
                relations=(), provenance=(), memory_ids=("hop1",),
            )
        if query == "O que está relacionado a PPPoE?":
            return SimpleNamespace(
                status="HIT",
                confidence=0.88,
                selected_context=self.second_context,
                relations=(), provenance=(), memory_ids=("hop2",),
            )
        return SimpleNamespace(status="UNRESOLVED", confidence=0.0, selected_context="", relations=(), provenance=(), memory_ids=())


def _chat(resolver):
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    adapter = CaptureAdapter()
    chat = ProductChatService(memory, adapter, conversation_resolver=resolver)
    scope = MemoryScope("org-a", application_id="offia", user_id="user-1", agent_id="offia:test")
    return chat, adapter, scope


def test_cat_question_is_enriched_by_memoria_before_llm_call():
    chat, adapter, scope = _chat(RelationalCatResolver())
    result = chat.run(scope=scope, message="Qual é o nome do meu gato?", mode="memoria")
    assert result.context == ("Alt é um gato do usuário. Vivi é um gato. Lay é um gato.",)
    assert adapter.calls == [("Qual é o nome do meu gato?", result.context)]


@pytest.mark.parametrize(
    ("message", "expected_probe"),
    [
        ("Qual é o nome do meu gato?", "Quais gatos você conhece?"),
        ("Qual é o modelo do meu carro?", "Quais carros você conhece?"),
        ("Qual é o IP do meu roteador?", "Quais roteadores você conhece?"),
        ("Como está minha bateria?", "Quais baterias você conhece?"),
        ("Qual é o estado do meu servidor?", "Quais servidores você conhece?"),
    ],
)
def test_possessive_relation_probe_is_domain_agnostic(message, expected_probe):
    assert _relation_probe_queries(message) == (expected_probe,)


def test_long_explanatory_input_does_not_expand_research_probe():
    assert _relation_probe_queries("Explique em detalhes como funciona uma bateria de lítio em sistemas embarcados") == ()


def test_non_possessive_router_question_activates_bounded_neighborhood():
    assert _relation_probe_queries("Qual o IP do roteador?") == (
        "O que está relacionado a IP?",
        "O que está relacionado a roteador?",
    )


def test_short_incident_activates_single_relevant_concept():
    assert _relation_probe_queries("A internet caiu") == ("O que está relacionado a internet?",)


def test_generic_activation_is_bounded_to_two_concepts():
    assert _relation_probe_queries("Roteador PPPoE OLT caiu?") == (
        "O que está relacionado a Roteador?",
        "O que está relacionado a PPPoE?",
    )


@pytest.mark.parametrize(
    ("message", "probe", "selected_context"),
    [
        ("Qual é o modelo do meu carro?", "Quais carros você conhece?", "Saveiro é um carro do usuário."),
        ("Qual é o IP do meu roteador?", "Quais roteadores você conhece?", "RB5009 é um roteador do usuário."),
        ("Como está minha bateria?", "Quais baterias você conhece?", "Bateria principal está carregada."),
        ("Qual o IP do roteador?", "O que está relacionado a roteador?", "roteador ip 192.168.88.1"),
    ],
)
def test_generic_question_probes_memory_before_llm(message, probe, selected_context):
    resolver = MissThenProbeHitResolver(probe, selected_context)
    chat, adapter, scope = _chat(resolver)
    result = chat.run(scope=scope, message=message, mode="memoria")
    assert (probe, "offia:test") in resolver.calls
    assert result.context
    assert adapter.calls == [(message, result.context)]
    assert result.metrics.memory_hits == 1


def test_two_hop_activation_reaches_pppoe_then_olt():
    resolver = TwoHopResolver()
    chat, adapter, scope = _chat(resolver)
    result = chat.run(scope=scope, message="A internet caiu", mode="memoria")

    assert resolver.calls == [
        ("A internet caiu", "offia:test"),
        ("A internet caiu", "profile:offia:user-1"),
        ("O que está relacionado a internet?", "offia:test"),
        ("O que está relacionado a PPPoE?", "offia:test"),
    ]
    assert result.context == ("internet PPPoE", "PPPoE | upstream | OLT")
    assert adapter.calls == [("A internet caiu", result.context)]


def test_two_hop_activation_stops_when_decayed_confidence_is_too_low():
    resolver = TwoHopResolver(first_confidence=0.5)
    chat, _adapter, scope = _chat(resolver)
    result = chat.run(scope=scope, message="A internet caiu", mode="memoria")

    assert resolver.calls == [
        ("A internet caiu", "offia:test"),
        ("A internet caiu", "profile:offia:user-1"),
        ("O que está relacionado a internet?", "offia:test"),
    ]
    assert result.context == ("internet PPPoE",)


def test_two_hop_context_budget_blocks_oversized_second_hop():
    resolver = TwoHopResolver(second_context="X" * 1400)
    chat, _adapter, scope = _chat(resolver)
    result = chat.run(scope=scope, message="A internet caiu", mode="memoria")

    assert len("\n".join(result.context)) <= 1200
    assert result.context == ("internet PPPoE",)


def test_real_memory_expands_possessive_cat_question_before_llm(tmp_path):
    evidence = ProductEvidenceService.open(tmp_path / "evidence", backend="sqlite", allow_fallback=True)
    resolver = ConversationSemanticService(evidence)
    namespace = "offia:conversation-real"
    resolver.ingest(role="user", text="Alt é um gato", session_id=namespace, order=1)
    resolver.ingest(role="user", text="Vivi é um gato", session_id=namespace, order=2)
    resolver.ingest(role="user", text="Lay é um gato", session_id=namespace, order=3)
    resolver.ingest(role="user", text="Meu gato é Alt", session_id=namespace, order=4)

    adapter = CaptureAdapter()
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    chat = ProductChatService(memory, adapter, conversation_resolver=resolver)
    scope = MemoryScope("org-a", application_id="offia", user_id="user-1", agent_id=namespace)
    result = chat.run(scope=scope, message="Qual é o nome do meu gato?", mode="memoria")

    assert result.metrics.memory_hits == 1
    assert result.context
    research = result.context[0]
    assert "Alt | is | gato" in research
    assert "Vivi | is | gato" in research
    assert "Lay | is | gato" in research


def test_enriched_provider_prompt_labels_memory_research_and_current_input():
    from memoria_resolutiva.openai_adapter import OpenAIResponsesAdapter

    prompt = OpenAIResponsesAdapter._input_text(
        "Qual é o nome do meu gato?",
        ["Alt é um gato do usuário.", "Vivi é um gato.", "Lay é um gato."],
    )
    assert prompt.startswith("PESQUISA DA MEMORIA.IA")
    assert "Memórias relacionadas:" in prompt
    assert "ENTRADA ATUAL" in prompt
    assert "Origem: user_text" in prompt
    assert "Conteúdo: Qual é o nome do meu gato?" in prompt
