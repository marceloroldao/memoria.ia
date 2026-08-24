from pathlib import Path

from memoria_resolutiva.autonomous_memory_v097 import AutonomousTextMemoryV097


def test_orion_recall_without_memory_key():
    memory = AutonomousTextMemoryV097()
    memory.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    memory.observe('Estou verificando um sistema local de memória.')
    memory.observe('A temperatura do laboratório hoje está agradável.')

    result = memory.query('Qual é o nome e a cor do meu carro de teste?')

    assert not result.abstained
    assert result.hits
    assert result.hits[0].text == 'Meu carro de teste se chama Orion e a cor dele é verde.'
    assert 'Orion' in result.hits[0].text
    assert 'verde' in result.hits[0].text


def test_distractors_do_not_displace_relevant_memory():
    memory = AutonomousTextMemoryV097()
    memory.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    for i in range(30):
        memory.observe(f'O sensor industrial número {i} registrou pressão estável no setor {i}.')

    result = memory.query('Qual é a cor do meu carro de teste?')
    assert result.hits[0].text.endswith('verde.')


def test_open_set_abstains():
    memory = AutonomousTextMemoryV097()
    memory.observe('Meu carro de teste se chama Orion e a cor dele é verde.')

    result = memory.query('Qual é a capital de um planeta que nunca foi mencionado?')
    assert result.abstained
    assert result.hits == ()


def test_exact_duplicate_does_not_multiply_records():
    memory = AutonomousTextMemoryV097()
    a = memory.observe('O projeto local usa memória persistente.')
    b = memory.observe('O projeto local usa memória persistente.')
    assert a.memory_id == b.memory_id
    assert len(memory) == 1


def test_polysemy_context_separates_database_from_park_bench():
    memory = AutonomousTextMemoryV097()
    memory.observe('O banco de dados do projeto usa persistência local e registros.')
    memory.observe('O banco da praça fica perto das árvores e do jardim.')

    db = memory.query('Como está a persistência do banco de dados do projeto?')
    park = memory.query('Onde fica o banco perto das árvores da praça?')

    assert db.hits and 'dados' in db.hits[0].text
    assert park.hits and 'praça' in park.hits[0].text


def test_conflicting_observations_are_both_preserved():
    memory = AutonomousTextMemoryV097()
    memory.observe('O carro de teste Orion está com a cor verde.')
    memory.observe('O carro de teste Orion está com a cor azul.')

    result = memory.query('Qual é a cor do carro de teste Orion?', top_k=3)
    texts = [hit.text for hit in result.hits]

    assert any('verde' in text for text in texts)
    assert any('azul' in text for text in texts)
    assert len(memory) == 2


def test_persistence_roundtrip_keeps_autonomous_recall(tmp_path: Path):
    path = tmp_path / 'autonomous.json'
    memory = AutonomousTextMemoryV097()
    memory.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    memory.save(path)

    restored = AutonomousTextMemoryV097.load(path)
    result = restored.query('Qual é o nome e a cor do meu carro de teste?')

    assert len(restored) == 1
    assert result.hits
    assert 'Orion' in result.hits[0].text
    assert 'verde' in result.hits[0].text


def test_candidate_index_avoids_full_scan_for_unrelated_query():
    memory = AutonomousTextMemoryV097()
    for i in range(200):
        memory.observe(f'Sensor {i} mede corrente elétrica no circuito módulo {i}.')
    memory.observe('Meu carro de teste se chama Orion e a cor dele é verde.')

    result = memory.query('Qual é a cor do meu carro de teste?')

    assert result.hits
    assert result.candidates_examined < len(memory)


def test_deterministic_ranking():
    memory = AutonomousTextMemoryV097()
    memory.observe('O dispositivo alfa usa bateria de lítio e sensor térmico.')
    memory.observe('O dispositivo beta usa bateria alcalina e sensor óptico.')

    first = memory.query('Qual dispositivo usa bateria de lítio?')
    second = memory.query('Qual dispositivo usa bateria de lítio?')

    assert first == second


def test_short_or_empty_noise_is_rejected():
    memory = AutonomousTextMemoryV097()
    try:
        memory.observe(' e de a ')
    except ValueError:
        pass
    else:
        raise AssertionError('meaningless observation should be rejected')
