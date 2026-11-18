#!/usr/bin/env python3
"""Synthetic native BDR windows -> read-only Python trajectory comparison."""
import argparse
import json
from pathlib import Path
import tempfile

from mobile_personal_proof_gate import OBSERVATIONS, QUERIES, region_rows, resolve
from mobile_region_replay import NativeProbe
from trajectory_contextual_hypothesis_probe import read
from trajectory_observed_variant_probe import score
from trajectory_response_quality_probe import TrajectoryGenerationExperiment, encode, decode

USER_KINDS = {'user_turn', 'user_assertion'}
KINDS = USER_KINDS | {'assistant_generated'}


def address(row):
    return row['hierarchy_id'], row['source_id'], row['sequence']


def adapt(rows, adapter):
    """Preserve input order and native scopes; excluded roles break the stream."""
    if adapter not in ('unicode', 'utf8'):
        raise ValueError('unsupported raw-symbol adapter')
    previous, identities, segments = {}, set(), {}
    memory = TrajectoryGenerationExperiment()
    provenance = {}
    for index, row in enumerate(rows):
        if (not isinstance(row, dict) or
            not all(isinstance(row.get(k), str) and row[k]
                    for k in ('hierarchy_id', 'source_id', 'text')) or
            type(row.get('sequence')) is not int or row['sequence'] < 0 or
            row.get('source_kind') not in KINDS):
            raise ValueError('invalid native observation')
        origin = address(row)
        scope = row['hierarchy_id']
        if origin in identities or row['sequence'] <= previous.get(scope, -1):
            raise ValueError('duplicate or unordered native address')
        identities.add(origin)
        previous[scope] = row['sequence']
        if row['source_kind'] not in USER_KINDS:
            segments[scope] = segments.get(scope, 0) + 1
            continue
        receipt = memory.observe(encode(row['text'], adapter),
            observation_id=f'native-row:{index}',
            stream_id=json.dumps((scope, segments.get(scope, 0))))
        provenance.setdefault(receipt.payload_id, []).append(origin)
    return memory, provenance


def fixtures():
    def row(source, region, sequence, text, kind='user_turn'):
        return dict(source_id=source, hierarchy_id='conversation:' + region,
                    sequence=sequence, text=text, source_kind=kind)
    isolated = [row(source, region, i+1, text, kind)
                for i, (source, region, text, kind) in enumerate(OBSERVATIONS[:-1])]
    paired = [row('known-q', 'known-pair', 1, QUERIES['known']),
              row('known-a', 'known-pair', 2, 'Meu drone se chama Auri.'),
              row('other-q', 'other-pair', 1, QUERIES['other_subject']),
              row('other-a', 'other-pair', 2, 'Meu robô se chama Lumo.')]
    conflicting = paired + [row('rival-q', 'rival-pair', 1, QUERIES['known']),
                            row('rival-a', 'rival-pair', 2, 'Meu drone se chama Boreal.')]
    barrier = [row('blocked-q', 'blocked', 1, QUERIES['known']),
               row('generated', 'blocked', 2, 'Meu drone se chama Falso.', 'assistant_generated'),
               row('later-user', 'blocked', 3, 'Meu drone se chama Auri.')] + paired[2:]
    return [('legacy_isolated', isolated), ('ordered_pairs', paired),
            ('ordered_conflict', conflicting), ('assistant_barrier', barrier)]


def descriptors(stage):
    known = (() if stage == 'assistant_barrier' else
             ('Meu drone se chama Auri.', 'Meu drone se chama Boreal.')
             if stage == 'ordered_conflict' else ('Meu drone se chama Auri.',))
    kind = 'absence' if not known else 'conflict' if len(known) == 2 else 'answer'
    return [('known', QUERIES['known'], kind, known),
            ('new_prefix', 'Lembre: ' + QUERIES['known'], kind, known),
            ('other_subject', QUERIES['other_subject'], 'answer', ('Meu robô se chama Lumo.',)),
            ('absent_recombination', QUERIES['absent_recombination'], 'absence', ())]


def evaluate(stage, rows, adapter):
    memory, provenance = adapt(rows, adapter)
    before = memory.snapshot(), memory.learning_state()
    cases = []
    for name, query, kind, targets in descriptors(stage):
        result = read(memory, encode(query, adapter))
        generation = result.generation
        witness_ids = {n.payload_id for n in generation.temporal_evidence}
        witness_ids.update(root for c in generation.candidates for step in c.steps
                           for root in step.supporting_payloads)
        if generation.association_evidence:
            witness_ids.update(root for c in generation.association_evidence.candidates
                               for source, target, _ in c.witnesses for root in (source, target))
        if generation.embedded_evidence:
            witness_ids.update(root for link in generation.embedded_evidence.links
                               for root in (link.cue_payload_id, link.target_payload_id))
        assert witness_ids <= provenance.keys(), 'unaddressable trajectory witness'
        hypothesis = None if result.hypothesis is None else decode(result.hypothesis, adapter)
        if hypothesis is not None:
            assert hypothesis[1], 'invalid symbol decoding'
        cases.append(dict(name=name, kind=kind, hypothesis=None if hypothesis is None else hypothesis[0],
            reason=result.reason, generation_mode=generation.mode,
            candidate_count=len(generation.candidates), ambiguous=generation.ambiguous,
            truncated=generation.truncated, witnesses_addressable=True,
            witness_source_count=sum(len(provenance[root]) for root in witness_ids),
            **score(result, tuple(encode(t, adapter) for t in targets), kind)))
    assert before == (memory.snapshot(), memory.learning_state())
    return dict(adapter=adapter, cases=cases, user_occurrences=len(memory.snapshot()['observations']),
                unique_user_payloads=len(provenance),
                quality_status='PASS' if all(c['quality_pass'] for c in cases) else 'FAIL')


def collect(probe, requested):
    by_address = {}
    for scope in dict.fromkeys(r['hierarchy_id'] for r in requested):
        for row in region_rows(probe, scope):
            value = {**row, 'hierarchy_id': scope}
            origin = address(value)
            if origin in by_address:
                raise RuntimeError('duplicate native window address')
            by_address[origin] = value
    if set(by_address) != {address(r) for r in requested}:
        raise RuntimeError('native window address set changed')
    ordered = [by_address[address(r)] for r in requested]
    for given, stored in zip(requested, ordered):
        if any(given[k] != stored[k] for k in given):
            raise RuntimeError('native observation changed')
    return ordered


def probe(library):
    stages = []
    for stage, inputs in fixtures():
        with tempfile.TemporaryDirectory(prefix='memoria-native-bridge-') as directory:
            native = NativeProbe(library, Path(directory))
            try:
                for row in inputs:
                    status, receipt = native.call('observe_structural_text', row)
                    if status != 0 or receipt['duplicate']:
                        raise RuntimeError('native input failed')
                warm = collect(native, inputs)
                native_warm = {name: resolve(native, query) for name, query in QUERIES.items()}
                native.reopen()
                cold = collect(native, inputs)
                native_cold = {name: resolve(native, query) for name, query in QUERIES.items()}
                if warm != cold or native_warm != native_cold:
                    raise RuntimeError('native cold reopen changed observations or evidence')
                adapted = [evaluate(stage, cold, adapter) for adapter in ('unicode', 'utf8')]
                for adapter in adapted:
                    if evaluate(stage, warm, adapter['adapter']) != adapter:
                        raise RuntimeError('native reopen changed trajectory result')
                native_summary = {name: dict(status=r['status'], qualified=r['qualified'],
                    candidate_count=len(r['contexts']),
                    top_source_id=r['contexts'][0]['source_id'] if r['contexts'] else None)
                    for name, r in native_cold.items()}
                legacy = None
                if stage == 'legacy_isolated':
                    legacy = dict(known_answer_first=native_summary['known']['top_source_id'] == 'answer-a',
                                  other_subject_first=native_summary['other_subject']['top_source_id'] == 'other-answer',
                                  absent_recombination_empty=not native_cold['absent_recombination']['contexts'])
                stages.append(dict(stage=stage, native_observations=len(cold), native_cold_parity=True,
                    native_unqualified=True, legacy_functional_gates=legacy,
                    native_cases=native_summary, trajectory=adapted,
                    quality_status='PASS' if all(a['quality_status']=='PASS' for a in adapted) else 'FAIL'))
            finally:
                native.close()
    cases = [c for stage in stages for adapter in stage['trajectory'] for c in adapter['cases']]
    counts = dict(cases=len(cases), passes=sum(c['quality_pass'] for c in cases),
                  answer_cases=sum(c['kind']=='answer' for c in cases),
                  correct_answers=sum(c['correct_answer'] for c in cases),
                  false_unique=sum(c['false_unique'] for c in cases),
                  absence_cases=sum(c['kind']=='absence' for c in cases),
                  absence_abstentions=sum(c['kind']=='absence' and c['hypothesis'] is None for c in cases),
                  conflict_cases=sum(c['kind']=='conflict' for c in cases),
                  conflicts_preserved=sum(c['kind']=='conflict' and c['quality_pass'] for c in cases))
    return dict(format='memoria.ia-native-trajectory-bridge-v1', integrity_status='PASS', counts=counts,
        quality_status='PASS' if all(s['quality_status']=='PASS' for s in stages) else 'FAIL',
        inference_activated_in_native=False, native_changed=False,
        adapter='raw_unicode_or_utf8_without_normalization', stages=stages)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.library)
    print(json.dumps(report, ensure_ascii=False, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status'] != 'PASS' else 0)
