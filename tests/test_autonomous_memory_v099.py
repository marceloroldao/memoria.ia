from memoria_resolutiva.autonomous_memory_v098 import AutonomousRecordV098, AutonomousTextMemoryV098, _terms
from memoria_resolutiva.autonomous_memory_v099 import AutonomousTextMemoryV099


def _seed(memory, texts):
    for text in texts:
        memory.observe(text)
    return memory


def _signature(result):
    return result.metrics.decision, result.abstained, tuple((h.text, round(h.score, 12)) for h in result.hits)


def test_v099_matches_v098_on_representative_corpus():
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

    baseline = _seed(AutonomousTextMemoryV098(), texts)
    adaptive = _seed(AutonomousTextMemoryV099(), texts)
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
        assert _signature(adaptive.query(query)) == _signature(baseline.query(query))
        assert adaptive.adaptive_stats().certified


def test_v099_reduces_exact_scoring_for_rare_discriminative_term():
    memory = AutonomousTextMemoryV099(candidate_ladder=(8, 16, 32, 64, 128))
    # All 100k distractors share one generic query term, so they are candidates,
    # but their mathematically safe upper bound stays below the acceptance threshold.
    total = 100_000
    for i in range(total):
        text = f'Projeto unidade sensor{i} rotina estável'
        record = AutonomousRecordV098(f'bulk:{i:08d}', text, _terms(text), i + 1, 'scale-gate')
        memory._index(record)
    target_text = 'Projeto Quasar telemetria orbital canal alfa pressão térmica central'
    target = AutonomousRecordV098('bulk:target', target_text, _terms(target_text), total + 1, 'scale-gate')
    memory._index(target)
    memory._sequence = total + 1

    result = memory.query('Projeto Quasar telemetria orbital canal alfa pressão térmica?')
    stats = memory.adaptive_stats()
    assert result.hits and 'Quasar' in result.hits[0].text
    assert stats.raw_candidates == total + 1
    assert stats.exact_scored <= 8
    assert stats.retained_fraction < 0.0001
    assert stats.certified
    assert stats.max_unseen_upper_bound < memory.threshold
    assert result.metrics.candidate_count == stats.exact_scored
    assert result.metrics.raw_candidate_count == stats.raw_candidates


def test_v099_expands_conservatively_when_small_prefix_is_ambiguous():
    memory = AutonomousTextMemoryV099(candidate_ladder=(4, 8, 16, 32), ambiguity_margin=0.20)
    for i in range(20):
        memory.observe(f'O sensor unidade {i} mede temperatura na sala comum.')
    result = memory.query('Qual sensor mede temperatura na sala comum?')
    stats = memory.adaptive_stats()
    assert result.abstained
    assert result.metrics.decision == 'unresolved'
    assert stats.expanded
    assert stats.exact_scored == stats.raw_candidates
    assert stats.certified


def test_v099_certificate_prevents_heuristic_prefix_misranking():
    # Same shared query terms give equal cheap priority, while record lengths make
    # exact v0.98 scores different. A heuristic prefix can stop on the wrong item;
    # the upper-bound certificate must continue until the true v0.98 winner is fixed.
    baseline = AutonomousTextMemoryV098()
    adaptive = AutonomousTextMemoryV099(candidate_ladder=(2, 4, 8), ambiguity_margin=0.01)
    records = [
        ('a-long', 'projeto quasar extra um dois três quatro cinco seis sete oito nove dez'),
        ('b-long', 'projeto quasar extra um dois três quatro cinco seis sete oito'),
        ('z-short', 'projeto quasar'),
    ]
    for seq, (mid, text) in enumerate(records, 1):
        for memory in (baseline, adaptive):
            record = AutonomousRecordV098(mid, text, _terms(text), seq, 'certificate-gate')
            memory._index(record)
            memory._sequence = seq
    query = 'projeto quasar'
    expected = baseline.query(query, top_k=1)
    actual = adaptive.query(query, top_k=1)
    assert _signature(actual) == _signature(expected)
    assert actual.hits and actual.hits[0].memory_id == 'z-short'
    assert adaptive.adaptive_stats().certified


def test_v099_exact_lookup_contract_is_unchanged():
    memory = AutonomousTextMemoryV099()
    observed = memory.observe('O módulo alfa está operacional.')
    record, metrics = memory.exact_lookup(observed.memory_id)
    assert record is not None
    assert metrics.exact_lookup_used is True
    assert metrics.semantic_discovery_latency_ms == 0.0
