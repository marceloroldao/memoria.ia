from memoria_resolutiva.autonomous_memory_v098 import AutonomousRecordV098, AutonomousTextMemoryV098, _terms
from memoria_resolutiva.autonomous_memory_v100 import AutonomousTextMemoryV100


def _signature(result):
    return result.metrics.decision, result.abstained, tuple((h.text, round(h.score, 12)) for h in result.hits)


def test_v100_matches_v098_on_representative_corpus():
    texts = [
        'Meu carro de teste se chama Orion e a cor dele é verde.',
        'A estação Vega usa o protocolo Nebulon para telemetria.',
        'O banco de dados do projeto usa persistência local e registros.',
        'O banco da praça fica perto das árvores e do jardim.',
        'O sensor alfa mede temperatura na sala norte.',
        'O sensor beta mede temperatura na sala sul.',
        'O módulo elétrico Delta usa bateria de lítio.',
        'A oficina mantém o inversor Sigma em modo de espera.',
    ]
    for i in range(240):
        texts.append(f'O dispositivo industrial {i} registra corrente estável no setor {i}.')

    baseline = AutonomousTextMemoryV098()
    candidate = AutonomousTextMemoryV100()
    for text in texts:
        baseline.observe(text)
        candidate.observe(text)
    queries = [
        'Qual é a cor do meu carro de teste?',
        'Qual protocolo a estação Vega usa?',
        'Como está a persistência do banco de dados do projeto?',
        'Onde fica o banco perto das árvores da praça?',
        'Qual sensor mede temperatura na sala norte?',
        'Qual módulo usa bateria de lítio?',
        'Qual inversor está em modo de espera?',
        'Onde está o submarino que nunca foi mencionado?',
    ]
    for query in queries:
        assert _signature(candidate.query(query)) == _signature(baseline.query(query))
        assert candidate.prefilter_stats().certified
        assert candidate.adaptive_stats().certified


def test_v100_prefilter_removes_generic_posting_mass_at_100k():
    memory = AutonomousTextMemoryV100()
    total = 100_000
    for i in range(total):
        text = f'Projeto unidade sensor{i} rotina estável'
        memory._index(AutonomousRecordV098(f'bulk:{i:08d}', text, _terms(text), i + 1, 'scale'))
    target_text = 'Projeto Quasar telemetria orbital canal alfa pressão térmica central'
    memory._index(AutonomousRecordV098('bulk:target', target_text, _terms(target_text), total + 1, 'scale'))
    memory._sequence = total + 1

    result = memory.query('Projeto Quasar telemetria orbital canal alfa pressão térmica?')
    pre = memory.prefilter_stats()
    adaptive = memory.adaptive_stats()
    assert result.hits and 'Quasar' in result.hits[0].text
    assert pre.certified
    assert pre.used
    assert pre.complement_upper_bound < memory.threshold
    assert pre.posting_pool_count < 100
    assert pre.scoring_mode == 'adaptive'
    assert adaptive.exact_scored <= 8


def test_v100_falls_back_to_broad_pool_when_query_is_too_generic():
    memory = AutonomousTextMemoryV100(one_shot_threshold=16)
    for i in range(30):
        memory.observe(f'O sensor unidade {i} mede temperatura na sala comum.')
    result = memory.query('Qual sensor mede temperatura na sala comum?')
    pre = memory.prefilter_stats()
    assert result.abstained
    assert pre.certified
    assert pre.scoring_mode == 'one_shot'
    assert memory.adaptive_stats().certified
    assert memory.adaptive_stats().exact_scored == pre.posting_pool_count


def test_v100_one_shot_generic_path_matches_v098():
    baseline = AutonomousTextMemoryV098(ambiguity_margin=0.20)
    candidate = AutonomousTextMemoryV100(ambiguity_margin=0.20, one_shot_threshold=8)
    for i in range(80):
        text = f'O sensor unidade {i} mede temperatura na sala comum.'
        baseline.observe(text)
        candidate.observe(text)
    expected = baseline.query('Qual sensor mede temperatura na sala comum?', top_k=5)
    actual = candidate.query('Qual sensor mede temperatura na sala comum?', top_k=5)
    assert _signature(actual) == _signature(expected)
    assert candidate.prefilter_stats().scoring_mode == 'one_shot'
    assert candidate.adaptive_stats().certified


def test_v100_prefilter_does_not_change_observe_conflict_path():
    memory = AutonomousTextMemoryV100()
    first = memory.observe('O carro de teste Orion está com a cor verde.')
    second = memory.observe('O carro de teste Orion está com a cor azul.')
    assert first.decision == 'distinct'
    assert second.decision == 'conflict'


def test_v100_exact_lookup_contract_unchanged():
    memory = AutonomousTextMemoryV100()
    observed = memory.observe('O módulo alfa está operacional.')
    record, metrics = memory.exact_lookup(observed.memory_id)
    assert record is not None
    assert metrics.exact_lookup_used is True
    assert metrics.semantic_discovery_latency_ms == 0.0
