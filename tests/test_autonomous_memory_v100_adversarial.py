from itertools import combinations

from memoria_resolutiva.autonomous_memory_v098 import AutonomousRecordV098, AutonomousTextMemoryV098, _terms
from memoria_resolutiva.autonomous_memory_v100 import AutonomousTextMemoryV100


def _signature(result):
    return (
        result.metrics.decision,
        result.abstained,
        tuple((h.memory_id, h.text, round(h.score, 12), h.relation) for h in result.hits),
    )


def _add(memory, mid: str, text: str, seq: int):
    record = AutonomousRecordV098(mid, text, _terms(text), seq, 'adversarial-v100')
    memory._index(record)
    memory._sequence = max(memory._sequence, seq)


def test_v100_exhaustive_shared_term_patterns_match_v098():
    vocabulary = ['projeto', 'quasar', 'telemetria', 'orbital', 'canal', 'pressão']
    baseline = AutonomousTextMemoryV098()
    candidate = AutonomousTextMemoryV100()
    seq = 0

    # Build every non-empty subset of the query vocabulary, with deterministic
    # noise length variations. This stresses the complement certificate because
    # exact scores vary even when shared-term counts are similar.
    for size in range(1, len(vocabulary) + 1):
        for combo in combinations(vocabulary, size):
            for noise in range(3):
                seq += 1
                suffix = ' '.join(f'ruido{noise}_{j}' for j in range(noise * 2))
                text = ' '.join(combo) + ((' ' + suffix) if suffix else '')
                mid = f'm:{seq:04d}'
                _add(baseline, mid, text, seq)
                _add(candidate, mid, text, seq)

    queries = [
        'projeto quasar telemetria orbital canal pressão',
        'quasar telemetria orbital canal pressão',
        'projeto quasar telemetria',
        'telemetria orbital canal',
        'projeto canal pressão',
        'quasar pressão',
        'projeto',
    ]
    for query in queries:
        for top_k in (1, 2, 3, 5):
            expected = baseline.query(query, top_k=top_k)
            actual = candidate.query(query, top_k=top_k)
            assert _signature(actual) == _signature(expected), (query, top_k)
            assert candidate.prefilter_stats().certified
            assert candidate.adaptive_stats().certified


def test_every_record_excluded_by_prefilter_is_below_threshold():
    baseline = AutonomousTextMemoryV098()
    candidate = AutonomousTextMemoryV100()
    texts = []
    for i in range(400):
        generic = f'projeto unidade setor{i} rotina estável'
        texts.append(generic)
    for i in range(40):
        texts.append(f'projeto telemetria canal unidade especial{i}')
    for i in range(10):
        texts.append(f'quasar telemetria orbital canal pressão alvo{i}')

    for seq, text in enumerate(texts, 1):
        mid = f'x:{seq:05d}'
        _add(baseline, mid, text, seq)
        _add(candidate, mid, text, seq)

    query = 'projeto quasar telemetria orbital canal pressão'
    qterms = _terms(query)
    candidate.query(query)
    required = set(candidate.prefilter_stats().required_any_terms)
    retained = set()
    for term in required:
        retained.update(candidate._inverted.get(term, ()))

    assert candidate.prefilter_stats().certified
    for mid, record in baseline._records.items():
        if mid not in retained:
            assert baseline._score(qterms, record.terms) < baseline.threshold


def test_v100_conflict_and_ambiguity_parity_under_prefilter():
    baseline = AutonomousTextMemoryV098(ambiguity_margin=0.20)
    candidate = AutonomousTextMemoryV100(ambiguity_margin=0.20)
    texts = [
        'O carro Orion está com a cor verde.',
        'O carro Orion está com a cor azul.',
        'O sensor alfa mede temperatura na sala norte.',
        'O sensor beta mede temperatura na sala sul.',
    ]
    for i in range(80):
        texts.append(f'O dispositivo {i} mede corrente no setor industrial {i}.')
    for text in texts:
        baseline.observe(text)
        candidate.observe(text)

    for query in (
        'Qual é a cor do carro Orion?',
        'Qual sensor mede temperatura na sala?',
        'Qual sensor mede temperatura na sala norte?',
    ):
        assert _signature(candidate.query(query, top_k=3)) == _signature(baseline.query(query, top_k=3))
