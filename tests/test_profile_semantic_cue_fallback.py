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

    def resolve(self, *, query: str, session_id: str | None = None):
        return SimpleNamespace(
            status="UNRESOLVED",
            confidence=0.0,
            selected_context="",
            relations=(),
            provenance=(),
            memory_ids=(),
        )


def _session_facts(core: EvidenceCore, namespace: str) -> None:
    core.observe_relation(
        "bateria",
        "is",
        "principal",
        evidence_id="session-battery",
        source_text="Minha bateria é a principal.",
        namespace=namespace,
    )
    core.observe_relation(
        "principal",
        "tensão",
        "48 V",
        evidence_id="session-voltage",
        source_text="A bateria principal está em 48 V.",
        namespace=namespace,
    )
    core.observe_relation(
        "principal",
        "corrente",
        "10 A",
        evidence_id="session-current",
        source_text="A bateria principal está em 10 A.",
        namespace=namespace,
    )


def _run(core: EvidenceCore):
    adapter = CaptureAdapter()
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    chat = ProductChatService(memory, adapter, conversation_resolver=EvidenceResolver(core))
    scope = MemoryScope(
        "org-a",
        application_id="offia",
        user_id="user-1",
        agent_id="offia:session-1",
    )
    result = chat.run(
        scope=scope,
        message="Com quantos volts está minha bateria?",
        mode="memoria",
    )
    return result, adapter


def test_session_fact_can_use_semantic_cue_from_same_users_profile():
    core = EvidenceCore()
    _session_facts(core, "offia:session-1")
    core.observe_relation(
        "volt",
        "unidade_de",
        "tensão",
        evidence_id="profile-unit-volt",
        source_text="Volt é unidade de tensão.",
        namespace="profile:offia:user-1",
    )

    result, adapter = _run(core)
    lines = result.context[0].splitlines()

    assert lines[0] == "bateria | is | principal"
    assert lines.index("principal | tensão | 48 V") < lines.index("principal | corrente | 10 A")
    assert all("unidade_de" not in line for line in lines)
    assert adapter.calls


def test_semantic_cue_from_another_users_profile_is_not_used():
    core = EvidenceCore()
    _session_facts(core, "offia:session-1")
    core.observe_relation(
        "volt",
        "unidade_de",
        "tensão",
        evidence_id="other-user-unit-volt",
        source_text="Volt é unidade de tensão.",
        namespace="profile:offia:user-2",
    )

    result, _adapter = _run(core)
    lines = result.context[0].splitlines()

    assert lines.index("principal | corrente | 10 A") < lines.index("principal | tensão | 48 V")
