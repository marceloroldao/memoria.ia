from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory
from time import perf_counter

from memoria_resolutiva.autonomous_memory_v097 import AutonomousTextMemoryV097


def run_gate(scale: int = 2000) -> dict:
    checks: dict[str, dict] = {}

    m = AutonomousTextMemoryV097()
    m.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    for i in range(50):
        m.observe(f'O módulo industrial série {i} monitora tensão no setor elétrico {i}.')
    q = m.query('Qual é o nome e a cor do meu carro de teste?')
    checks['product_orion'] = {
        'pass': bool(q.hits and 'Orion' in q.hits[0].text and 'verde' in q.hits[0].text),
        'best_score': q.metrics.best_score,
        'candidate_count': q.metrics.candidate_count,
        'latency_ms': q.metrics.semantic_discovery_latency_ms,
    }

    unseen = [
        'Qual é a capital do planeta nunca mencionado?',
        'Quem venceu uma corrida que não foi registrada?',
        'Qual receita culinária foi armazenada?',
        'Onde está o submarino desconhecido?',
        'Qual é a senha secreta inexistente?',
    ]
    open_results = [m.query(text) for text in unseen]
    abstain_rate = sum(r.abstained for r in open_results) / len(open_results)
    checks['open_set'] = {'pass': abstain_rate == 1.0, 'abstention_rate': abstain_rate}

    p = AutonomousTextMemoryV097()
    p.observe('O banco de dados do projeto usa persistência local e registros.')
    p.observe('O banco da praça fica perto das árvores e do jardim.')
    db = p.query('Como está a persistência do banco de dados do projeto?')
    park = p.query('Onde fica o banco perto das árvores da praça?')
    checks['polysemy'] = {
        'pass': bool(db.hits and park.hits and 'dados' in db.hits[0].text and 'praça' in park.hits[0].text),
        'db_score': db.metrics.best_score,
        'park_score': park.metrics.best_score,
    }

    c = AutonomousTextMemoryV097()
    c.observe('O carro de teste Orion está com a cor verde.')
    conflict_decision = c.observe('O carro de teste Orion está com a cor azul.')
    cq = c.query('Qual é a cor do carro de teste Orion?', top_k=3)
    ctexts = [hit.text for hit in cq.hits]
    checks['conflict'] = {
        'pass': conflict_decision.decision == 'conflict' and cq.metrics.decision == 'conflict' and any('verde' in t for t in ctexts) and any('azul' in t for t in ctexts),
        'observation_decision': conflict_decision.decision,
        'query_decision': cq.metrics.decision,
        'selected_count': cq.metrics.selected_count,
    }

    with TemporaryDirectory() as td:
        path = Path(td) / 'memory.json'
        m.save(path)
        restored = AutonomousTextMemoryV097.load(path)
        rq = restored.query('Qual é o nome e a cor do meu carro de teste?')
        checks['restart'] = {
            'pass': bool(rq.hits and q.hits and rq.hits[0].memory_id == q.hits[0].memory_id and rq.metrics.best_score == q.metrics.best_score),
            'score_before': q.metrics.best_score,
            'score_after': rq.metrics.best_score,
        }

    s = AutonomousTextMemoryV097()
    for i in range(scale):
        s.observe(f'Arquivo técnico lote {i} contém telemetria hidráulica componente exclusivo{i}.')
    target = s.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    semantic_times = []
    candidate_counts = []
    for _ in range(20):
        r = s.query('Qual é a cor do meu carro de teste?')
        semantic_times.append(r.metrics.semantic_discovery_latency_ms)
        candidate_counts.append(r.metrics.candidate_count)
    exact_times = []
    for _ in range(100):
        _, metrics = s.exact_lookup(target.memory_id)
        exact_times.append(metrics.exact_lookup_latency_ms)
    checks['scaling'] = {
        'pass': max(candidate_counts) < len(s) and bool(s.query('Qual é a cor do meu carro de teste?').hits),
        'records': len(s),
        'candidate_count_max': max(candidate_counts),
        'semantic_latency_ms_mean': mean(semantic_times),
        'exact_lookup_latency_ms_mean': mean(exact_times),
    }

    d = AutonomousTextMemoryV097()
    d.observe('O dispositivo alfa usa bateria de lítio e sensor térmico.')
    d.observe('O dispositivo beta usa bateria alcalina e sensor óptico.')
    signatures = []
    for _ in range(20):
        r = d.query('Qual dispositivo usa bateria de lítio?')
        signatures.append([(h.memory_id, h.score, h.relation) for h in r.hits])
    checks['determinism'] = {'pass': all(sig == signatures[0] for sig in signatures), 'runs': len(signatures)}

    passed = all(item['pass'] for item in checks.values())
    return {
        'format': 'memoria.ia-autonomous-v097-gate-1',
        'passed': passed,
        'neural_or_external_calls': 0,
        'checks': checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--scale', type=int, default=2000)
    parser.add_argument('--output', default='benchmark-results/autonomous-v097-gate.json')
    parser.add_argument('--fail-on-fail', action='store_true')
    args = parser.parse_args()
    report = run_gate(args.scale)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if args.fail_on_fail and not report['passed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
