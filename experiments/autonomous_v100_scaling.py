from __future__ import annotations

import json
from time import perf_counter

from memoria_resolutiva.autonomous_memory_v098 import AutonomousRecordV098, AutonomousTextMemoryV098, _terms
from memoria_resolutiva.autonomous_memory_v099 import AutonomousTextMemoryV099
from memoria_resolutiva.autonomous_memory_v100 import AutonomousTextMemoryV100


def build(total: int):
    memories = [AutonomousTextMemoryV098(), AutonomousTextMemoryV099(), AutonomousTextMemoryV100()]
    for i in range(total):
        text = f'Projeto unidade sensor{i} rotina estável'
        terms = _terms(text)
        for memory in memories:
            memory._index(AutonomousRecordV098(f'bulk:{i:08d}', text, terms, i + 1, 'scaling'))
    target_text = 'Projeto Quasar telemetria orbital canal alfa pressão térmica central'
    terms = _terms(target_text)
    for memory in memories:
        memory._index(AutonomousRecordV098('bulk:target', target_text, terms, total + 1, 'scaling'))
    return memories


def timed(memory, query: str):
    start = perf_counter()
    result = memory.query(query)
    return result, (perf_counter() - start) * 1000.0


def run(total: int):
    v098, v099, v100 = build(total)
    query = 'Projeto Quasar telemetria orbital canal alfa pressão térmica?'
    r98, ms98 = timed(v098, query)
    r99, ms99 = timed(v099, query)
    r100, ms100 = timed(v100, query)
    assert r98.hits and r99.hits and r100.hits
    assert r98.hits[0].text == r99.hits[0].text == r100.hits[0].text
    pre = v100.prefilter_stats()
    adaptive = v100.adaptive_stats()
    return {
        'memories': total + 1,
        'v098_ms': ms98,
        'v099_ms': ms99,
        'v100_ms': ms100,
        'v099_speedup_vs_v098': ms98 / ms99 if ms99 else None,
        'v100_speedup_vs_v098': ms98 / ms100 if ms100 else None,
        'v100_speedup_vs_v099': ms99 / ms100 if ms100 else None,
        'v100_posting_pool': pre.posting_pool_count,
        'v100_required_any_terms': pre.required_any_terms,
        'v100_prefilter_certified': pre.certified,
        'v100_exact_scored': adaptive.exact_scored,
        'v100_scoring_certified': adaptive.certified,
    }


if __name__ == '__main__':
    print(json.dumps({'cases': [run(10_000), run(100_000)]}, indent=2, sort_keys=True))
