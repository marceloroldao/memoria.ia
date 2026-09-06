from types import SimpleNamespace

from memoria_resolutiva.llm_adapter import LLMResponse, LLMUsage
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


class RelationalCatResolver:
    def __init__(self):
        self.calls = []

    def resolve(self, *, query: str, session_id: str | None = None):
        self.calls.append((query, session_id))
        return SimpleNamespace(
            status="HIT",
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


def test_cat_question_is_enriched_by_memoria_before_llm_call():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    resolver = RelationalCatResolver()
    adapter = CaptureAdapter()
    chat = ProductChatService(memory, adapter, conversation_resolver=resolver)
    scope = MemoryScope(
        "org-a",
        application_id="offia",
        user_id="user-1",
        agent_id="offia:conversation-1",
    )

    result = chat.run(
        scope=scope,
        message="Qual é o nome do meu gato?",
        mode="memoria",
    )

    expected_context = (
        "Alt é um gato do usuário.\nVivi é um gato.\nLay é um gato.",
    )
    assert resolver.calls == [
        ("Qual é o nome do meu gato?", "offia:conversation-1"),
    ]
    assert adapter.calls == [
        ("Qual é o nome do meu gato?", expected_context),
    ]
    assert result.context == expected_context
    assert result.metrics.memory_hits == 1
    assert result.metrics.memory_misses == 0


def test_enriched_provider_prompt_labels_memory_research_and_current_input():
    from memoria_resolutiva.openai_adapter import OpenAIResponsesAdapter

    prompt = OpenAIResponsesAdapter._input_text(
        "Qual é o nome do meu gato?",
        [
            "Alt é um gato do usuário.",
            "Vivi é um gato.",
            "Lay é um gato.",
        ],
    )

    assert prompt.startswith("PESQUISA DA MEMORIA.IA")
    assert "Memórias relacionadas:" in prompt
    assert "- Alt é um gato do usuário." in prompt
    assert "- Vivi é um gato." in prompt
    assert "- Lay é um gato." in prompt
    assert "ENTRADA ATUAL" in prompt
    assert "Origem: user_text" in prompt
    assert "Conteúdo: Qual é o nome do meu gato?" in prompt
