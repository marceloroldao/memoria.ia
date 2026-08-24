from pathlib import Path

from memoria_resolutiva.autonomous_memory_v097 import AutonomousTextMemoryV097
from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


def build(tmp_path: Path):
    enterprise = EnterpriseMemoryService(OrganizationIdentity('org-auto'))
    scope = MemoryScope('org-auto', application_id='web')
    auto = AutonomousTextMemoryV097()
    snapshot = tmp_path / 'autonomous-memory-v097.json'
    chat = ProductChatService(enterprise, MockLLMAdapter(), autonomous_memory=auto, autonomous_snapshot=snapshot)
    return chat, scope, snapshot


def test_chat_stores_statement_then_recalls_without_memory_keys(tmp_path: Path):
    chat, scope, snapshot = build(tmp_path)

    first = chat.run(
        scope=scope,
        message='Meu carro de teste se chama Orion e a cor dele é verde.',
        mode='memoria',
    )
    assert first.context == ()
    assert first.metrics.autonomous_memories_created == 1
    assert snapshot.exists()

    second = chat.run(
        scope=scope,
        message='Qual é o nome e a cor do meu carro de teste?',
        mode='memoria',
    )
    assert second.metrics.memory_hits >= 1
    assert second.metrics.memory_misses == 0
    assert second.metrics.autonomous_selected >= 1
    assert second.metrics.autonomous_best_score >= 0.42
    assert second.context
    assert 'Orion' in second.context[0]
    assert 'verde' in second.context[0]


def test_question_is_not_stored_as_memory(tmp_path: Path):
    chat, scope, _ = build(tmp_path)
    chat.run(scope=scope, message='Qual é a capital de Marte?', mode='memoria')
    assert len(chat.autonomous_memory) == 0


def test_autonomous_state_survives_chat_restart(tmp_path: Path):
    chat, scope, snapshot = build(tmp_path)
    chat.run(scope=scope, message='Meu carro de teste se chama Orion e a cor dele é verde.', mode='memoria')

    restored_auto = AutonomousTextMemoryV097.load(snapshot)
    enterprise = EnterpriseMemoryService(OrganizationIdentity('org-auto'))
    restarted = ProductChatService(
        enterprise,
        MockLLMAdapter(),
        autonomous_memory=restored_auto,
        autonomous_snapshot=snapshot,
    )
    result = restarted.run(scope=scope, message='Qual é a cor do meu carro de teste?', mode='memoria')
    assert result.metrics.memory_hits >= 1
    assert result.context and 'verde' in result.context[0]


def test_manual_key_path_remains_backward_compatible(tmp_path: Path):
    chat, scope, _ = build(tmp_path)
    chat.memory.remember(scope, 'k1', 'customer plan is pro', ('key', 'customer.plan'))
    result = chat.run(
        scope=scope,
        message='what is the plan?',
        mode='memoria',
        memory_keys=['customer.plan'],
    )
    assert result.context == ('customer plan is pro',)
    assert result.metrics.memory_hits == 1
    assert result.metrics.autonomous_candidates == 0
    assert len(chat.autonomous_memory) == 0


def test_open_set_question_abstains_without_polluting_memory(tmp_path: Path):
    chat, scope, _ = build(tmp_path)
    chat.run(scope=scope, message='Meu carro de teste se chama Orion e a cor dele é verde.', mode='memoria')
    result = chat.run(scope=scope, message='Onde está o submarino desconhecido?', mode='memoria')
    assert result.metrics.memory_hits == 0
    assert result.metrics.memory_misses == 1
    assert result.metrics.autonomous_abstentions == 1
    assert len(chat.autonomous_memory) == 1
