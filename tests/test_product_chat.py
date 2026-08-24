from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_chat import ProductChatService, token_reduction
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


def build():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a"))
    scope = MemoryScope("org-a", application_id="chat")
    memory.remember(scope, "k1", "customer plan is pro", ("key", "customer.plan"))
    memory.remember(scope, "k2", "invoice is overdue", ("key", "invoice.status"))
    return ProductChatService(memory, MockLLMAdapter()), scope


def test_memoria_mode_reports_hit_and_miss():
    chat, scope = build()
    result = chat.run(
        scope=scope,
        message="what is the plan?",
        mode="memoria",
        memory_keys=["customer.plan", "missing"],
    )
    assert result.context == ("customer plan is pro",)
    assert result.metrics.memory_hits == 1
    assert result.metrics.memory_misses == 1
    assert result.metrics.external_calls == 1
    assert result.metrics.provider == "mock"


def test_baseline_sends_full_context_without_memory_resolution():
    chat, scope = build()
    result = chat.run(
        scope=scope,
        message="what is the plan?",
        mode="baseline",
        baseline_context=["customer plan is pro", "invoice is overdue", "irrelevant repeated history"],
    )
    assert len(result.context) == 3
    assert result.metrics.memory_hits == 0
    assert result.metrics.memory_misses == 0
    assert result.metrics.memory_latency_ms == 0.0


def test_token_reduction_is_calculated_from_observed_values():
    assert token_reduction(baseline_tokens=100, memoria_tokens=40) == 0.6
    assert token_reduction(baseline_tokens=0, memoria_tokens=0) is None


def test_memoria_mode_can_reduce_context_in_controlled_fixture():
    chat, scope = build()
    baseline = chat.run(
        scope=scope,
        message="what is the plan?",
        mode="baseline",
        baseline_context=[
            "customer plan is pro",
            "invoice is overdue",
            "irrelevant repeated history " * 8,
        ],
    )
    memoria = chat.run(
        scope=scope,
        message="what is the plan?",
        mode="memoria",
        memory_keys=["customer.plan"],
    )
    reduction = token_reduction(
        baseline_tokens=baseline.metrics.input_tokens,
        memoria_tokens=memoria.metrics.input_tokens,
    )
    assert reduction is not None
    assert reduction > 0
