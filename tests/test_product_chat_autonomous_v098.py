from pathlib import Path

from memoria_resolutiva.autonomous_memory_v098 import AutonomousTextMemoryV098
from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


def build(tmp_path: Path):
    enterprise = EnterpriseMemoryService(OrganizationIdentity('org-auto-v098'))
    scope = MemoryScope('org-auto-v098', application_id='web')
    auto = AutonomousTextMemoryV098()
    snapshot = tmp_path / 'autonomous-memory-v098.json'
    chat = ProductChatService(enterprise, MockLLMAdapter(), autonomous_memory=auto, autonomous_snapshot=snapshot)
    return chat, scope, snapshot


def test_chat_v098_stores_and_recalls_without_keys(tmp_path: Path):
    chat, scope, snapshot = build(tmp_path)
    first = chat.run(scope=scope, message='Meu carro de teste se chama Orion e a cor dele é verde.', mode='memoria')
    assert first.metrics.autonomous_memories_created == 1
    assert first.metrics.autonomous_indexed == 1
    assert snapshot.exists()

    second = chat.run(scope=scope, message='Qual é o nome e a cor do meu carro de teste?', mode='memoria')
    assert second.metrics.memory_hits >= 1
    assert second.metrics.autonomous_selected >= 1
    assert second.metrics.autonomous_indexed == 1
    assert second.metrics.autonomous_raw_candidates >= 1
    assert second.context and 'Orion' in second.context[0] and 'verde' in second.context[0]


def test_chat_v098_restart_preserves_context(tmp_path: Path):
    chat, scope, snapshot = build(tmp_path)
    chat.run(scope=scope, message='O equipamento Atlas usa marcador Quasar.', mode='memoria')
    restored = AutonomousTextMemoryV098.load(snapshot)
    restarted = ProductChatService(
        EnterpriseMemoryService(OrganizationIdentity('org-auto-v098')),
        MockLLMAdapter(),
        autonomous_memory=restored,
        autonomous_snapshot=snapshot,
    )
    result = restarted.run(scope=scope, message='Qual equipamento usa o marcador Quasar?', mode='memoria')
    assert result.metrics.memory_hits >= 1
    assert result.context and 'Atlas' in result.context[0]


def test_chat_v098_open_set_abstains_without_writing_question(tmp_path: Path):
    chat, scope, _ = build(tmp_path)
    chat.run(scope=scope, message='O equipamento Atlas usa marcador Quasar.', mode='memoria')
    result = chat.run(scope=scope, message='Onde fica a estação lunar desconhecida?', mode='memoria')
    assert result.metrics.memory_hits == 0
    assert result.metrics.autonomous_abstentions == 1
    assert len(chat.autonomous_memory) == 1
