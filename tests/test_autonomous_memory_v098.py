from pathlib import Path

from memoria_resolutiva.autonomous_memory_v097 import AutonomousTextMemoryV097
from memoria_resolutiva.autonomous_memory_v098 import AutonomousTextMemoryV098


def test_v098_keeps_orion_baseline_behavior():
    memory = AutonomousTextMemoryV098()
    memory.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    memory.observe('Estou verificando um sistema local de memória.')
    result = memory.query('Qual é o nome e a cor do meu carro de teste?')
    assert not result.abstained
    assert result.hits[0].text == 'Meu carro de teste se chama Orion e a cor dele é verde.'
    assert result.metrics.decision == 'related'


def _fill_common_noise(memory, count: int = 800):
    memory.observe('O projeto sistema usa memória e protocolo comum.')
    memory.observe('O projeto Atlas usa protocolo Quasar para sincronização orbital.')
    for i in range(count):
        memory.observe(f'Projeto sistema memória protocolo comum registro{i}.')


def test_rare_term_weighting_beats_common_vocabulary_noise():
    baseline = AutonomousTextMemoryV097()
    improved = AutonomousTextMemoryV098()
    _fill_common_noise(baseline)
    _fill_common_noise(improved)
    query = 'Qual projeto sistema memória protocolo Quasar?'

    old = baseline.query(query)
    new = improved.query(query)

    assert new.hits
    assert 'Quasar' in new.hits[0].text
    assert new.metrics.best_score > new.metrics.runner_up_score
    # This corpus is intentionally adversarial for the unweighted v0.97 scorer:
    # generic terms outnumber the single rare discriminative term.
    assert not old.hits or 'Quasar' not in old.hits[0].text


def test_v098_open_set_still_abstains():
    memory = AutonomousTextMemoryV098()
    memory.observe('O veículo Orion usa bateria de lítio.')
    result = memory.query('Qual é a capital do planeta Netuno?')
    assert result.abstained
    assert result.metrics.decision == 'unresolved'
    assert result.metrics.abstentions == 1


def test_v098_ambiguity_still_abstains():
    memory = AutonomousTextMemoryV098(ambiguity_margin=0.20)
    memory.observe('O sensor alfa mede temperatura na sala norte.')
    memory.observe('O sensor beta mede temperatura na sala sul.')
    result = memory.query('Qual sensor mede temperatura na sala?')
    assert result.abstained
    assert result.metrics.decision == 'unresolved'


def test_v098_conflicts_are_preserved():
    memory = AutonomousTextMemoryV098()
    first = memory.observe('O carro de teste Orion está com a cor verde.')
    second = memory.observe('O carro de teste Orion está com a cor azul.')
    assert first.decision == 'distinct'
    assert second.decision == 'conflict'
    result = memory.query('Qual é a cor do carro de teste Orion?', top_k=3)
    texts = [hit.text for hit in result.hits]
    assert result.metrics.decision == 'conflict'
    assert any('verde' in text for text in texts)
    assert any('azul' in text for text in texts)


def test_v098_persistence_rebuilds_rarity_statistics(tmp_path: Path):
    path = tmp_path / 'v098.json'
    memory = AutonomousTextMemoryV098()
    _fill_common_noise(memory, 100)
    before = memory.query('Qual projeto usa protocolo Quasar?')
    memory.save(path)
    restored = AutonomousTextMemoryV098.load(path)
    after = restored.query('Qual projeto usa protocolo Quasar?')
    assert [(h.memory_id, h.text, h.score) for h in before.hits] == [(h.memory_id, h.text, h.score) for h in after.hits]
    assert before.metrics.decision == after.metrics.decision


def test_v098_deterministic_ranking():
    memory = AutonomousTextMemoryV098()
    memory.observe('O dispositivo alfa usa bateria de lítio e sensor térmico.')
    memory.observe('O dispositivo beta usa bateria alcalina e sensor óptico.')
    a = memory.query('Qual dispositivo usa bateria de lítio?')
    b = memory.query('Qual dispositivo usa bateria de lítio?')
    assert [(h.memory_id, h.score, h.relation) for h in a.hits] == [(h.memory_id, h.score, h.relation) for h in b.hits]


def test_v098_10k_index_keeps_sparse_query_candidate_set_small():
    memory = AutonomousTextMemoryV098()
    for i in range(10_000):
        memory.observe(f'registro{i} assinatura{i}')
    memory.observe('O veículo especial Orion possui marcador Quasar verde.')
    result = memory.query('Orion Quasar verde')
    assert result.hits
    assert 'Orion' in result.hits[0].text
    assert result.metrics.indexed_count == 10_001
    assert result.metrics.raw_candidate_count < 20
    assert result.candidates_examined == result.metrics.raw_candidate_count


def test_v098_exact_lookup_remains_separate_resolved_path():
    memory = AutonomousTextMemoryV098()
    decision = memory.observe('O módulo alfa está operacional.')
    record, metrics = memory.exact_lookup(decision.memory_id)
    assert record is not None
    assert metrics.exact_lookup_used is True
    assert metrics.semantic_discovery_latency_ms == 0.0
