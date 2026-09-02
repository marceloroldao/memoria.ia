from types import SimpleNamespace

from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_chat import ProductChatService, profile_namespace
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


class FakeConversationResolver:
    def __init__(self, responses=None, status="HIT", selected_context="O gato se chama Alt."):
        self.responses = responses or {}
        self.status = status
        self.selected_context = selected_context
        self.calls = []

    def resolve(self, *, query: str, session_id: str | None = None):
        self.calls.append((query, session_id))
        status, selected = self.responses.get(session_id, (self.status, self.selected_context))
        return SimpleNamespace(status=status, selected_context=selected)


def test_memoria_chat_resolves_context_automatically_from_session():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    resolver = FakeConversationResolver()
    chat = ProductChatService(memory, MockLLMAdapter(), conversation_resolver=resolver)
    scope = MemoryScope("org-a", application_id="web", agent_id="web:conversation-1")

    result = chat.run(
        scope=scope,
        message="Qual é o nome do gato?",
        mode="memoria",
        memory_keys=[],
    )

    assert resolver.calls == [("Qual é o nome do gato?", "web:conversation-1")]
    assert result.context == ("O gato se chama Alt.",)
    assert result.metrics.memory_hits == 1
    assert result.metrics.memory_misses == 0
    assert result.metrics.context_sent_chars == len("O gato se chama Alt.")


def test_memoria_chat_falls_back_to_profile_after_session_miss():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    resolver = FakeConversationResolver(responses={
        "web:new-conversation": ("UNRESOLVED", ""),
        "profile:web": ("HIT", "O gato se chama Alt."),
    })
    chat = ProductChatService(memory, MockLLMAdapter(), conversation_resolver=resolver)
    scope = MemoryScope("org-a", application_id="web", agent_id="web:new-conversation")

    result = chat.run(
        scope=scope,
        message="Qual é o nome do gato?",
        mode="memoria",
        memory_keys=[],
    )

    assert profile_namespace(scope) == "profile:web"
    assert resolver.calls == [
        ("Qual é o nome do gato?", "web:new-conversation"),
        ("Qual é o nome do gato?", "profile:web"),
    ]
    assert result.context == ("O gato se chama Alt.",)
    assert result.metrics.memory_hits == 1
    assert result.metrics.memory_misses == 0


def test_memoria_chat_records_automatic_context_miss_without_inventing_context():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    resolver = FakeConversationResolver(status="MISS", selected_context="")
    chat = ProductChatService(memory, MockLLMAdapter(), conversation_resolver=resolver)
    scope = MemoryScope("org-a", application_id="web", agent_id="web:conversation-2")

    result = chat.run(
        scope=scope,
        message="Algo que ainda não foi aprendido",
        mode="memoria",
        memory_keys=[],
    )

    assert resolver.calls == [
        ("Algo que ainda não foi aprendido", "web:conversation-2"),
        ("Algo que ainda não foi aprendido", "profile:web"),
    ]
    assert result.context == ()
    assert result.metrics.memory_hits == 0
    assert result.metrics.memory_misses == 1
