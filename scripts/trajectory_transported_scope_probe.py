#!/usr/bin/env python3
"""Opt-in transported source discriminator, with recorded or live native input."""
import argparse
from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
from unittest.mock import patch

import trajectory_native_bridge_probe as bridge
import trajectory_contextual_hypothesis_probe as contextual
from trajectory_response_quality_probe import TrajectoryGenerationExperiment, encode


class TransportedScopeExperiment(TrajectoryGenerationExperiment):
    def contextual_route_hypothesis(self, payload, **options):
        options.setdefault('transported_source_scope', True)
        return super().contextual_route_hypothesis(payload, **options)


@contextmanager
def enabled_adapter():
    with patch.object(bridge, 'TrajectoryGenerationExperiment', TransportedScopeExperiment), \
         patch.object(contextual, 'TrajectoryGenerationExperiment', TransportedScopeExperiment):
        yield


def checked_read(memory, query, **options):
    before = memory.snapshot(), memory.learning_state()
    default = memory.contextual_route_hypothesis(query, **options)
    generation = asdict(memory.generate(query, **options))
    result = memory.contextual_route_hypothesis(query, transported_source_scope=True, **options)
    cold = TrajectoryGenerationExperiment.restore(memory.snapshot())
    assert asdict(result) == asdict(cold.contextual_route_hypothesis(
        query, transported_source_scope=True, **options))
    assert generation == asdict(result.generation) == asdict(memory.generate(query, **options))
    assert before == (memory.snapshot(), memory.learning_state())
    assert asdict(default) == asdict(memory.contextual_route_hypothesis(query, **options))
    return result


def probe(library=None):
    reference = json.loads((Path(__file__).resolve().parents[1] /
        'benchmark-results/trajectory-native-bridge-report.json').read_text())
    stages = []
    for stage, rows in bridge.fixtures():
        default = [bridge.evaluate(stage, rows, adapter) for adapter in ('unicode', 'utf8')]
        assert default == next(s for s in reference['stages'] if s['stage'] == stage)['trajectory']
        with enabled_adapter():
            experimental = [bridge.evaluate(stage, rows, adapter) for adapter in ('unicode', 'utf8')]
        diagnostics = []
        for adapter in ('unicode', 'utf8'):
            memory, provenance = bridge.adapt(rows, adapter)
            for name, query, _, _ in bridge.descriptors(stage):
                result = checked_read(memory, encode(query, adapter))
                assert all(s in provenance and t in provenance
                           for s, t, _ in result.scoped_out_witnesses)
                diagnostics.append(dict(adapter=adapter, name=name, reason=result.reason,
                    scoped_out_witnesses=result.scoped_out_witnesses,
                    contextual_fragments=result.contextual_fragments,
                    default_generation_unchanged=True, cold_parity=True, learning_unchanged=True))
        stages.append(dict(stage=stage, recorded_native_baseline_parity=True,
                           default=default, experimental=experimental, diagnostics=diagnostics))
    def counts(key):
        cases = [c for s in stages for a in s[key] for c in a['cases']]
        return dict(cases=len(cases), passed=sum(c['quality_pass'] for c in cases),
                    correct_answers=sum(c['correct_answer'] for c in cases),
                    answer_cases=sum(c['kind'] == 'answer' for c in cases),
                    false_unique=sum(c['false_unique'] for c in cases),
                    absence_abstentions=sum(c['kind'] == 'absence' and c['hypothesis'] is None for c in cases),
                    conflicts_preserved=sum(c['kind'] == 'conflict' and c['quality_pass'] for c in cases))
    native = None
    if library is not None:
        with enabled_adapter():
            native = bridge.probe(library)
        for stage in stages:
            assert stage['experimental'] == next(
                s for s in native['stages'] if s['stage'] == stage['stage'])['trajectory']
    experimental_counts = counts('experimental')
    return dict(format='memoria.ia-transported-source-scope-v2', integrity_status='PASS',
                hypothesis_revision='transported-common-subspan-v1',
                quality_status='PASS' if experimental_counts['passed'] == experimental_counts['cases'] else 'FAIL',
                policy_status='EXPERIMENTAL_OPT_IN', default_hypothesis_changed=False,
                default_generation_changed=False, native_changed=False, inference_activated_in_native=False,
                native_executed=library is not None, default_counts=counts('default'),
                experimental_counts=experimental_counts, stages=stages, native_evaluation=native)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.library)
    print(json.dumps(report, ensure_ascii=False, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status'] != 'PASS' else 0)
