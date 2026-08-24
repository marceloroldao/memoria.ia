from pathlib import Path

from memoria_resolutiva.autonomous_memory_v097 import AutonomousTextMemoryV097


def test_orion_recall_without_memory_key():
    memory = AutonomousTextMemoryV097()
    observed = memory.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    memory.observe('Estou verificando um sistema local de memória.')
    memory.observe('A temperatura do laboratório hoje está agradável.')
    result = memory.query('Qual é o nome e a cor do meu carro de teste?')
    assert observed.decision == 'distinct'
    assert not result.abstained
    assert result.hits
    assert result.hits[0].text == 'Meu carro de teste se chama Orion e a cor dele é verde.'
    assert result.metrics.candidate_count >= 1
    assert result.metrics.selected_count >= 1
    assert result.metrics.best_score >= memory.threshold


def test_distractors_do_not_displace_relevant_memory():
    memory = AutonomousTextMemoryV097()
    memory.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    for i in range(30):
        memory.observe(f'O sensor industrial número {i} registrou pressão estável no setor {i}.')
    result = memory.query('Qual é a cor do meu carro de teste?')
    assert result.hits[0].text.endswith('verde.')


def test_open_set_abstains_and_reports_unresolved():
    memory = AutonomousTextMemoryV097(); memory.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    result = memory.query('Qual é a capital de um planeta que nunca foi mencionado?')
    assert result.abstained and result.hits == () and result.metrics.decision == 'unresolved'


def test_exact_duplicate_reinforces_without_multiplying_records():
    memory = AutonomousTextMemoryV097(); a = memory.observe('O projeto local usa memória persistente.'); b = memory.observe('O projeto local usa memória persistente.')
    assert a.memory_id == b.memory_id and b.decision == 'same' and b.metrics.memories_reinforced == 1 and len(memory) == 1


def test_polysemy_context_separates_database_from_park_bench():
    memory = AutonomousTextMemoryV097(); memory.observe('O banco de dados do projeto usa persistência local e registros.'); memory.observe('O banco da praça fica perto das árvores e do jardim.')
    db = memory.query('Como está a persistência do banco de dados do projeto?'); park = memory.query('Onde fica o banco perto das árvores da praça?')
    assert db.hits and 'dados' in db.hits[0].text and park.hits and 'praça' in park.hits[0].text


def test_conflicting_observations_are_classified_and_preserved():
    memory = AutonomousTextMemoryV097(); first = memory.observe('O carro de teste Orion está com a cor verde.'); second = memory.observe('O carro de teste Orion está com a cor azul.')
    assert first.decision == 'distinct' and second.decision == 'conflict' and first.memory_id in second.related_memory_ids
    result = memory.query('Qual é a cor do carro de teste Orion?', top_k=3); texts = [hit.text for hit in result.hits]
    assert result.metrics.decision == 'conflict' and any('verde' in t for t in texts) and any('azul' in t for t in texts)


def test_persistence_roundtrip_reproduces_ranking_and_decision(tmp_path: Path):
    path = tmp_path / 'autonomous.json'; memory = AutonomousTextMemoryV097(); memory.observe('Meu carro de teste se chama Orion e a cor dele é verde.'); before = memory.query('Qual é o nome e a cor do meu carro de teste?'); memory.save(path)
    restored = AutonomousTextMemoryV097.load(path); after = restored.query('Qual é o nome e a cor do meu carro de teste?')
    assert [h.memory_id for h in before.hits] == [h.memory_id for h in after.hits] and before.metrics.best_score == after.metrics.best_score


def test_candidate_index_avoids_full_scan():
    memory = AutonomousTextMemoryV097()
    for i in range(200): memory.observe(f'Sensor {i} mede corrente elétrica no circuito módulo {i}.')
    memory.observe('Meu carro de teste se chama Orion e a cor dele é verde.'); result = memory.query('Qual é a cor do meu carro de teste?')
    assert result.hits and result.candidates_examined < len(memory)


def test_deterministic_ranking_ignoring_wall_clock_metric():
    memory = AutonomousTextMemoryV097(); memory.observe('O dispositivo alfa usa bateria de lítio e sensor térmico.'); memory.observe('O dispositivo beta usa bateria alcalina e sensor óptico.')
    first = memory.query('Qual dispositivo usa bateria de lítio?'); second = memory.query('Qual dispositivo usa bateria de lítio?')
    assert [(h.memory_id,h.score,h.relation) for h in first.hits] == [(h.memory_id,h.score,h.relation) for h in second.hits]


def test_exact_lookup_is_separate_resolved_address_path():
    memory = AutonomousTextMemoryV097(); decision = memory.observe('O módulo alfa está operacional.'); record, metrics = memory.exact_lookup(decision.memory_id)
    assert record is not None and metrics.exact_lookup_used is True and metrics.semantic_discovery_latency_ms == 0.0


def test_ambiguous_non_conflicting_query_abstains():
    memory = AutonomousTextMemoryV097(ambiguity_margin=0.20); memory.observe('O sensor alfa mede temperatura na sala norte.'); memory.observe('O sensor beta mede temperatura na sala sul.')
    result = memory.query('Qual sensor mede temperatura na sala?'); assert result.abstained and result.metrics.decision == 'unresolved'


def test_short_or_empty_noise_is_rejected():
    memory = AutonomousTextMemoryV097()
    try: memory.observe(' e de a ')
    except ValueError: pass
    else: raise AssertionError('meaningless observation should be rejected')
