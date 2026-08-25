from __future__ import annotations

import json
from time import perf_counter

from memoria_resolutiva.autonomous_memory_v098 import AutonomousRecordV098, AutonomousTextMemoryV098, _terms
from memoria_resolutiva.autonomous_memory_v099 import AutonomousTextMemoryV099
from memoria_resolutiva.autonomous_memory_v100 import AutonomousTextMemoryV100


def add(memory, mid: str, text: str, seq: int):
    memory._index(AutonomousRecordV098(mid, text, _terms(text), seq, 'selectivity'))


def build(total: int = 100_000):
    memories = [AutonomousTextMemoryV098(), AutonomousTextMemoryV099(), AutonomousTextMemoryV100()]
    for i in range(total):
        if i < 100:
            text = f'projeto telemetria orbital grupo-raro unidade{i}'
        elif i < 10_000:
            text = f'projeto telemetria setor-medio unidade{i}'
        else:
            text = f'projeto rotina setor-generico unidade{i}'
        for memory in memories:
            add(memory, f'm:{i:06d}', text, i + 1)
    target = 'projeto telemetria orbital quasar canal pressão alvo-central'
    for memory in memories:
        add(memory, 'target', target, total + 1)
    return memories


def timed(memory, query: str):
    start = perf_counter()
    result = memory.query(query)
    return result, (perf_counter() - start) * 1000.0


def run_case(memories, name: str, query: str):
    v98, v99, v100 = memories
    r98, t98 = timed(v98, query)
    r99, t99 = timed(v99, query)
    r100, t100 = timed(v100, query)
    sig98 = (r98.metrics.decision, tuple(h.memory_id for h in r98.hits))
    sig99 = (r99.metrics.decision, tuple(h.memory_id for h in r99.hits))
    sig100 = (r100.metrics.decision, tuple(h.memory_id for h in r100.hits))
    if not (sig98 == sig99 == sig100):
        raise SystemExit(f'parity failure for {name}: {sig98} {sig99} {sig100}')
    pre = v100.prefilter_stats()
    adapt = v100.adaptive_stats()
    return {
        'name': name,
        'query': query,
        'v098_ms': t98,
        'v099_ms': t99,
        'v100_ms': t100,
        'v100_speedup_vs_v098': t98 / t100 if t100 else None,
        'v100_speedup_vs_v099': t99 / t100 if t100 else None,
        'posting_pool': pre.posting_pool_count,
        'prefilter_used': pre.used,
        'prefilter_certified': pre.certified,
        'exact_scored': adapt.exact_scored,
        'scoring_certified': adapt.certified,
        'decision': r100.metrics.decision,
    }


if __name__ == '__main__':
    memories = build()
    cases = [
        run_case(memories, 'high_selectivity', 'projeto telemetria orbital quasar canal pressão'),
        run_case(memories, 'medium_selectivity', 'projeto telemetria setor-medio'),
        run_case(memories, 'low_selectivity', 'projeto rotina setor-generico'),
        run_case(memories, 'generic_only', 'projeto'),
    ]
    print(json.dumps({'memories': len(memories[0]), 'cases': cases}, indent=2, sort_keys=True))
