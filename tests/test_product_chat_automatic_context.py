from types import SimpleNamespace

from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_chat import ProductChatService, profile_namespace
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


class FakeConversationResolver:
    def __init__(
        self,
        responses=None,
        status="HIT",
        selected_context="O gato se chama Alt.",
        relations=(),
        provenance=(),
        memory_ids=(),
    ):
        self.responses = responses or {}
        self.status = status
        self.selected_context = selected_context
        self.relations = relations
        self.provenance = provenance
        self.memory_ids = memory_ids
        self.calls = []

    def resolve(self, *, query: str, session_id: str | None = None):
        self.calls.append((query, session_id))
        configured = self.responses.get(session_id)
        if configured is not None:
            if isinstance(configured, SimpleNamespace):
                return configured
            status, selected = configured
            return SimpleNamespace(
                status=status,
                selected_context=selected,
                relations=(),
                provenance=(),
                memory_ids=(),
            )
        return SimpleNamespace(
            status=self.status,
            selected_context=self.selected_context,
            relations=self.relations,
            provenance=self.provenance,
            memory_ids=self.memory_ids,
        )


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


def test_single_strong_factual_relation_is_compacted_before_llm():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    selected = "O usuário informou claramente que o nome atual do gato doméstico é Alt."
    resolver = FakeConversationResolver(
        selected_context=selected,
        relations=({
            "subject": "gato",
            "predicate": "is",
            "object": "Alt",
            "confidence": 0.95,
            "memory_id": "r1",
        },),
        provenance=({"memory_id": "r1", "source_type": "derived_relation"},),
        memory_ids=("r1",),
    )
    chat = ProductChatService(memory, MockLLMAdapter(), conversation_resolver=resolver)
    scope = MemoryScope("org-a", application_id="web", agent_id="web:conversation-3")

    result = chat.run(scope=scope, message="Qual é o nome do gato?", mode="memoria")

    assert result.context == ("gato | is | Alt",)
    assert result.metrics.retrieved_context_chars == len(selected)
    assert result.metrics.context_sent_chars == len("gato | is | Alt")
    assert result.metrics.context_sent_chars < result.metrics.retrieved_context_chars


def test_weak_relation_keeps_original_context():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    selected = "O motor parece ser um V8 segundo uma forma elíptica de baixa confiança."
    resolver = FakeConversationResolver(
        selected_context=selected,
        relations=({
            "subject": "motor",
            "predicate": "is",
            "object": "V8",
            "confidence": 0.85,
            "memory_id": "r2",
        },),
        provenance=({"memory_id": "r2", "source_type": "derived_relation"},),
        memory_ids=("r2",),
    )
    chat = ProductChatService(memory, MockLLMAdapter(), conversation_resolver=resolver)
    scope = MemoryScope("org-a", application_id="web", agent_id="web:conversation-4")

    result = chat.run(scope=scope, message="Qual motor?", mode="memoria")

    assert result.context == (selected,)
    assert result.metrics.retrieved_context_chars == result.metrics.context_sent_chars


def test_temporal_context_is_never_compacted_even_with_one_strong_relation():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    selected = "CURRENT: bateria carregada"
    resolver = FakeConversationResolver(
        selected_context=selected,
        relations=({
            "subject": "bateria",
            "predicate": "is",
            "object": "carregada",
            "confidence": 0.95,
            "memory_id": "r3",
        },),
        provenance=({"memory_id": "r3", "source_type": "derived_relation"},),
        memory_ids=("r3",),
    )
    chat = ProductChatService(memory, MockLLMAdapter(), conversation_resolver=resolver)
    scope = MemoryScope("org-a", application_id="web", agent_id="web:conversation-5")

    result = chat.run(scope=scope, message="Como está a bateria agora?", mode="memoria")

    assert result.context == (selected,)


def test_multiple_provenance_rows_keep_original_context():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    selected = "Duas fontes independentes confirmam que a bateria está carregada."
    resolver = FakeConversationResolver(
        selected_context=selected,
        relations=({
            "subject": "bateria",
            "predicate": "is",
            "object": "carregada",
            "confidence": 0.95,
            "memory_id": "r4",
        },),
        provenance=(
            {"memory_id": "u1", "source_type": "user_assertion"},
            {"memory_id": "u2", "source_type": "user_assertion"},
        ),
        memory_ids=("r4",),
    )
    chat = ProductChatService(memory, MockLLMAdapter(), conversation_resolver=resolver)
    scope = MemoryScope("org-a", application_id="web", agent_id="web:conversation-6")

    result = chat.run(scope=scope, message="Estado da bateria?", mode="memoria")

    assert result.context == (selected,)
