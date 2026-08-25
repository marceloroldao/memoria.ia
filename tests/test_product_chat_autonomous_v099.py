from pathlib import Path

from memoria_resolutiva.autonomous_memory_v099 import AutonomousTextMemoryV099
from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


def build(tmp_path: Path):
    enterprise = EnterpriseMemoryService(OrganizationIdentity('org-v099'))
    scope = MemoryScope('org-v099', application_id='web')
    auto = AutonomousTextMemoryV099()
    snapshot = tmp_path / 'autonomous-memory-v098.json'
    chat = ProductChatService(enterprise, MockLLMAdapter(), autonomous_memory=auto, autonomous_snapshot=snapshot)
    return chat, scope, snapshot


def test_v099_chat_stores_and_recalls_with_certificate_metrics(tmp_path: Path):
    chat, scope, snapshot = build(tmp_path)
    first = chat.run(scope=scope, message='Meu carro de teste se chama Orion e a cor dele é verde.', mode='memoria')
    assert first.metrics.autonomous_memories_created == 1
    assert snapshot.exists()

    second = chat.run(scope=scope, message='Qual é o nome e a cor do meu carro de teste?', mode='memoria')
    assert second.metrics.memory_hits >= 1
    assert second.metrics.autonomous_selected >= 1
    assert second.metrics.autonomous_pruning_certified is True
    assert second.metrics.autonomous_raw_candidates >= second.metrics.autonomous_candidates
    assert 0.0 <= second.metrics.autonomous_retained_fraction <= 1.0
    assert second.metrics.autonomous_max_unseen_upper_bound >= 0.0
    assert second.context and 'Orion' in second.context[0] and 'verde' in second.context[0]


def test_v099_chat_state_survives_restart(tmp_path: Path):
    chat, scope, snapshot = build(tmp_path)
    chat.run(scope=scope, message='A estação Vega usa o protocolo Nebulon para telemetria.', mode='memoria')

    restored = AutonomousTextMemoryV099.load(snapshot)
    restarted = ProductChatService(
        EnterpriseMemoryService(OrganizationIdentity('org-v099')),
        MockLLMAdapter(),
        autonomous_memory=restored,
        autonomous_snapshot=snapshot,
    )
    result = restarted.run(scope=scope, message='Qual protocolo a estação Vega usa?', mode='memoria')
    assert result.metrics.memory_hits >= 1
    assert result.metrics.autonomous_pruning_certified is True
    assert result.context and 'Nebulon' in result.context[0]


def test_v099_manual_key_path_stays_backward_compatible(tmp_path: Path):
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
    assert result.metrics.autonomous_raw_candidates == 0
    assert result.metrics.autonomous_pruning_certified is False
    assert len(chat.autonomous_memory) == 0
