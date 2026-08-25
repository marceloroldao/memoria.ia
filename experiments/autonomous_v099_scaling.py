from __future__ import annotations

import json
from time import perf_counter

from memoria_resolutiva.autonomous_memory_v098 import AutonomousRecordV098, AutonomousTextMemoryV098, _terms
from memoria_resolutiva.autonomous_memory_v099 import AutonomousTextMemoryV099


def build_pair(total: int):
    baseline = AutonomousTextMemoryV098()
    adaptive = AutonomousTextMemoryV099()
    for i in range(total):
        text = f'Projeto unidade sensor{i} rotina estável'
        terms = _terms(text)
        record_a = AutonomousRecordV098(f'bulk:{i:08d}', text, terms, i + 1, 'scaling')
        record_b = AutonomousRecordV098(f'bulk:{i:08d}', text, terms, i + 1, 'scaling')
        baseline._index(record_a)
        adaptive._index(record_b)
    target_text = 'Projeto Quasar telemetria orbital canal alfa pressão térmica central'
    terms = _terms(target_text)
    baseline._index(AutonomousRecordV098('bulk:target', target_text, terms, total + 1, 'scaling'))
    adaptive._index(AutonomousRecordV098('bulk:target', target_text, terms, total + 1, 'scaling'))
    return baseline, adaptive


def timed(memory, query: str):
    start = perf_counter()
    result = memory.query(query)
    elapsed = (perf_counter() - start) * 1000.0
    return result, elapsed


def run(total: int):
    baseline, adaptive = build_pair(total)
    query = 'Projeto Quasar telemetria orbital canal alfa pressão térmica?'
    b, b_ms = timed(baseline, query)
    a, a_ms = timed(adaptive, query)
    stats = adaptive.adaptive_stats()
    if not b.hits or not a.hits or b.hits[0].text != a.hits[0].text:
        raise SystemExit('v0.99 result diverged from v0.98 baseline')
    return {
        'memories': total + 1,
        'v098_ms': b_ms,
        'v099_ms': a_ms,
        'speedup': (b_ms / a_ms) if a_ms else None,
        'raw_candidates': stats.raw_candidates,
        'exact_scored': stats.exact_scored,
        'retained_fraction': stats.retained_fraction,
        'certified': stats.certified,
    }


if __name__ == '__main__':
    report = {'cases': [run(10_000), run(100_000)]}
    print(json.dumps(report, indent=2, sort_keys=True))
