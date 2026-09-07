from __future__ import annotations

from types import SimpleNamespace

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.llm_adapter import LLMResponse, LLMUsage
from memoria_resolutiva.product_chat import ProductChatService
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


class EvidenceResolver:
    def __init__(self, core: EvidenceCore):
        self.evidence = SimpleNamespace(core=core)
        self.resolve_calls = []

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


def _build_core(namespace: str, *, include_unit_relation: bool) -> EvidenceCore:
    core = EvidenceCore()
    core.observe_relation(
        "bateria",
        "is",
        "principal",
        evidence_id="battery-owner",
        source_text="Minha bateria é a principal.",
        namespace=namespace,
    )
    core.observe_relation(
        "principal",
        "tensão",
        "48 V",
        evidence_id="battery-voltage",
        source_text="A bateria principal está em 48 V.",
        namespace=namespace,
    )
    core.observe_relation(
        "principal",
        "corrente",
        "10 A",
        evidence_id="battery-current",
        source_text="A bateria principal está em 10 A.",
        namespace=namespace,
    )
    if include_unit_relation:
        core.observe_relation(
            "volt",
            "unidade_de",
            "tensão",
            evidence_id="unit-volt",
            source_text="Volt é unidade de tensão.",
            namespace=namespace,
        )
    return core


def _run(include_unit_relation: bool):
    namespace = "profile:offia:user-1"
    resolver = EvidenceResolver(_build_core(namespace, include_unit_relation=include_unit_relation))
    adapter = CaptureAdapter()
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    chat = ProductChatService(memory, adapter, conversation_resolver=resolver)
    scope = MemoryScope("org-a", application_id="offia", user_id="user-1")
    message = "Com quantos volts está minha bateria?"
    result = chat.run(scope=scope, message=message, mode="memoria")
    return result, adapter, message


def test_product_chat_uses_unit_of_relation_from_memory_to_rank_predicate():
    result, adapter, message = _run(include_unit_relation=True)

    assert result.metrics.memory_hits == 1
    lines = result.context[0].splitlines()
    assert lines[0] == "bateria | is | principal"
    assert lines.index("principal | tensão | 48 V") < lines.index("principal | corrente | 10 A")
    assert all("unidade_de" not in line for line in lines)
    assert adapter.calls == [(message, result.context)]


def test_product_chat_has_no_hidden_builtin_volts_to_voltage_mapping():
    result, _adapter, _message = _run(include_unit_relation=False)

    lines = result.context[0].splitlines()
    assert lines.index("principal | corrente | 10 A") < lines.index("principal | tensão | 48 V")
