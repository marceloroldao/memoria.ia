from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.address_trajectory_conversation_v2 import (
    AddressTrajectoryConversationResolverV2,
)
from memoria_resolutiva.native_resolve import NativeResolveService
from memoria_resolutiva.product_identity import MemoryScope


def _scope() -> MemoryScope:
    return MemoryScope("org-v2", application_id="server", agent_id="session-v2")


def _seed_facts() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato e da cor verde")
    memory.ingest("meu carro e da cor azul")
    memory.ingest("minha camisa e da cor preta")
    return memory


def test_zero_llm_native_resolution_uses_trajectory_geometry_only():
    memory = _seed_facts()
    before = memory.snapshot()
    native = NativeResolveService(
        AddressTrajectoryConversationResolverV2(memory),
        min_confidence=0.75,
    )

    result = native.resolve(
        scope=_scope(),
        message="qual a cor da minha camisa?",
    )

    assert result.status == "RESOLVED"
    assert result.text == "preta"
    assert result.confidence == 1.0
    assert result.external_calls == 0
    assert memory.snapshot() == before


def test_equal_structural_evidence_remains_unresolved_instead_of_guessing():
    memory = AddressTrajectoryMemory()
    memory.ingest("minha camisa e da cor preta")
    memory.ingest("minha camisa e da cor azul")
    native = NativeResolveService(AddressTrajectoryConversationResolverV2(memory))

    result = native.resolve(
        scope=_scope(),
        message="qual a cor da minha camisa?",
    )

    assert result.status == "UNRESOLVED"
    assert result.text is None
    assert result.external_calls == 0


def test_unknown_intention_remains_unresolved_without_external_call():
    memory = _seed_facts()
    native = NativeResolveService(AddressTrajectoryConversationResolverV2(memory))

    result = native.resolve(
        scope=_scope(),
        message="senha roteador inexistente",
    )

    assert result.status == "UNRESOLVED"
    assert result.text is None
    assert result.external_calls == 0


def test_adapter_has_no_domain_dependency():
    memory = AddressTrajectoryMemory()
    memory.ingest("x7 q2 r9 zeta")
    memory.ingest("x8 q3 r4 omega")
    native = NativeResolveService(AddressTrajectoryConversationResolverV2(memory))

    result = native.resolve(
        scope=_scope(),
        message="probe x7 q2 r9",
    )

    assert result.status == "RESOLVED"
    assert result.text == "zeta"
    assert result.external_calls == 0
