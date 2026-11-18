#!/usr/bin/env python3
"""Rejected shadow policy: carried fragments versus distinct source support."""
from dataclasses import asdict, replace
import json
from pathlib import Path
from unittest.mock import patch

import trajectory_native_bridge_probe as bridge
import trajectory_contextual_hypothesis_probe as contextual
from trajectory_response_quality_probe import TrajectoryGenerationExperiment, encode


def contains(part, whole):
    return any(whole[i:i + len(part)] == part
               for i in range(len(whole) - len(part) + 1))


class ShadowFragmentScope(TrajectoryGenerationExperiment):
    """Evaluation only; never installed in the runtime or default generator."""
    def contextual_route_hypothesis(self, payload, *, hierarchy_id='default', **options):
        query = tuple(payload)
        baseline = super().contextual_route_hypothesis(
            query, hierarchy_id=hierarchy_id, **options)
        generation = baseline.generation
        if generation.mode != 'COMBINED_RECALL' or generation.truncated:
            return baseline
        embedded = generation.embedded_evidence
        targets = {n.payload_id for n in generation.temporal_evidence}
        if embedded:
            targets.update(link.target_payload_id for link in embedded.links)
        association = generation.association_evidence
        if len(targets) != 1 or association is None:
            return baseline
        target = next(iter(targets))
        symbols = self.expand(target)
        cues = {self.expand(link.cue_payload_id) for link in embedded.links} if embedded else set()
        if embedded is None or self.temporal_neighbors(query, hierarchy_id=hierarchy_id):
            cues.add(query)
        scoped = set()
        for candidate in association.candidates:
            if not candidate.witnesses:
                return baseline
            own_sources = {s for s, t, _ in candidate.witnesses if t == target}
            for source, destination, stream in candidate.witnesses:
                if destination == target:
                    continue
                source_symbols = self.expand(source)
                # Rejected relaxation: any own witness or carried fragment
                # replaces separate support from this particular source.
                if ((not own_sources and not contains(candidate.symbols, source_symbols))
                    or contains(source_symbols, query)
                    or any(contains(cue, source_symbols) for cue in cues)):
                    return baseline
                scoped.add((source, destination, stream))
        for candidate in generation.candidates:
            if not contains(candidate.output, symbols) and not any(
                candidate.output == a.symbols and a.witnesses and
                all(contains(a.symbols, self.expand(source)) for source, _, _ in a.witnesses)
                for a in association.candidates
            ):
                return baseline
        return replace(baseline, hypothesis=symbols, reason='SHADOW_FRAGMENT_SCOPE',
            contextual_fragments=tuple(c.output for c in generation.candidates if c.output != symbols),
            shared_source_contexts=tuple(sorted(cues)), scoped_out_witnesses=tuple(sorted(scoped)))


def unsupported_origin(adapter, renamed):
    transform = lambda text: tuple(10000 - x if renamed else x for x in encode(text, adapter))
    memory = ShadowFragmentScope()
    for i, (query, answer) in enumerate((('Código de Daro?', 'Daro: 791.'),
                                       ('código de daro?', 'Daro: 415.'))):
        memory.observe(transform(query), observation_id=f'{i}:q', stream_id=str(i))
        memory.observe(transform(answer), observation_id=f'{i}:a', stream_id=str(i))
    query = transform('Código de Daro?')
    before = memory.snapshot(), memory.learning_state()
    generation = asdict(memory.generate(query))
    result = memory.contextual_route_hypothesis(query)
    cold = ShadowFragmentScope.restore(memory.snapshot())
    assert asdict(result) == asdict(cold.contextual_route_hypothesis(query))
    assert generation == asdict(result.generation) == asdict(memory.generate(query))
    assert before == (memory.snapshot(), memory.learning_state())
    current = TrajectoryGenerationExperiment.restore(memory.snapshot()).contextual_route_hypothesis(query)
    assert current.hypothesis is None
    return dict(adapter=adapter, renamed=renamed, expected='abstention',
                baseline_abstains=True, shadow_abstains=result.hypothesis is None,
                contract_pass=result.hypothesis is None,
                shadow_hypothesis=result.hypothesis, scoped_out_witnesses=result.scoped_out_witnesses,
                full_generation=generation, cold_parity=True, learning_unchanged=True)


def probe():
    stages = []
    reference = json.loads((Path(__file__).resolve().parents[1] /
        'benchmark-results/trajectory-native-bridge-report.json').read_text())
    for stage, rows in bridge.fixtures():
        original = [bridge.evaluate(stage, rows, adapter) for adapter in ('unicode', 'utf8')]
        native_record = next(s for s in reference['stages'] if s['stage'] == stage)
        assert original == native_record['trajectory'], 'recorded native reference changed'
        with patch.object(bridge, 'TrajectoryGenerationExperiment', ShadowFragmentScope), \
             patch.object(contextual, 'TrajectoryGenerationExperiment', ShadowFragmentScope):
            shadow = [bridge.evaluate(stage, rows, adapter) for adapter in ('unicode', 'utf8')]
        stages.append(dict(stage=stage, recorded_native_baseline_parity=True,
                           baseline=original, shadow=shadow))
    contracts = [unsupported_origin(adapter, renamed)
                 for adapter in ('unicode', 'utf8') for renamed in (False, True)]
    def counts(key):
        cases = [c for stage in stages for a in stage[key] for c in a['cases']]
        return dict(cases=len(cases), passed=sum(c['quality_pass'] for c in cases),
                    correct_answers=sum(c['correct_answer'] for c in cases),
                    answer_cases=sum(c['kind'] == 'answer' for c in cases),
                    false_unique=sum(c['false_unique'] for c in cases),
                    absence_abstentions=sum(c['kind'] == 'absence' and c['hypothesis'] is None for c in cases),
                    conflicts_preserved=sum(c['kind'] == 'conflict' and c['quality_pass'] for c in cases))
    return dict(format='memoria.ia-fragment-scope-ablation-v1', integrity_status='PASS',
                policy_status='REJECTED' if any(not c['contract_pass'] for c in contracts) else 'UNRESOLVED',
                engine_changed=False, native_executed_in_this_probe=False,
                default_generation_unchanged=True, baseline_counts=counts('baseline'),
                shadow_counts=counts('shadow'), unsupported_origin_controls=contracts, stages=stages)


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False, separators=(',', ':')))
