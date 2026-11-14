#!/usr/bin/env python3
"""Occurrence-addressed witness rejection; preserve independent remaining support."""
import argparse
import json
from pathlib import Path
from random import Random
from string import ascii_lowercase, digits
import tempfile

from mobile_region_replay import NativeProbe
from trajectory_addressed_feedback_probe import (
    addressed_read, operations, projection, record_addressed, target_packet,
    withdraw_addressed, witness_occurrence_map,
)
from trajectory_feedback_continuity_probe import historical_proofs
from trajectory_feedback_ledger_probe import canonical, receipt
from trajectory_question_frame_probe import collect, persist, score
from trajectory_region_evidence_probe import fingerprint
from trajectory_route_feedback_probe import make_fixture
from trajectory_route_relation_probe import read


def witness_request(frame_id, witness, occurrence):
    result = dict(kind='WITNESS', frame_id=frame_id, witness=witness)
    for role in ('source', 'target'):
        row = occurrence[role]
        result[role + '_address'] = [row['hierarchy_id'], row['source_id'], row['sequence']]
    return result


def witness_read(native, region, query, *, enabled=False):
    base = addressed_read(native, region, query, enabled=enabled, _allow_witness=True)
    base.update(format='memoria.ia-occurrence-witness-feedback-view-v1', witness_feedback_enabled=enabled)
    if not enabled:
        return base
    rows = collect(native, [region])
    active = [dict(address=p['address'], event=p['event'])
              for p in projection(operations(native, region)) if p['active'] and p['event']['target']['kind'] == 'WITNESS']
    proofs = historical_proofs(rows, active)
    support = witness_occurrence_map(rows, region)
    rejected, evidence = {}, []
    for entry in active:
        event = entry['event']
        target = event['target']
        proof = proofs.get(event['receipt']['receipt_id'])
        reproduced = False
        if proof is not None:
            prefix = rows[:proof['prefix_rows']]
            historical = read(prefix, region, event['receipt']['query'])
            expected = target_packet(historical, event['receipt'],
                witness_request(target['frame']['frame_id'], target['witness'], target['occurrence']), rows=prefix)
            reproduced = canonical(expected) == canonical(target)
        current = canonical(target['occurrence']) in {canonical(p) for p in support.get(canonical(target['witness']), [])}
        evidence.append(dict(feedback=entry, historical_target_reproduced=reproduced,
                             current_occurrence_matches=current))
        if reproduced and current and event['stance'] == 'oppose':
            key = canonical((target['witness'], target['occurrence']))
            rejected.setdefault(key, []).append(entry)
    blocked, diagnostics = {}, {}
    for frame in base['raw_view']['frames']:
        exhausted = []
        for witness in frame['witnesses']:
            occurrences = support.get(canonical(witness), [])
            if not occurrences:
                raise ValueError('learned witness has no addressable native occurrence')
            remaining = [p for p in occurrences if canonical((witness, p)) not in rejected]
            diagnostic = diagnostics.setdefault(canonical(witness), dict(witness=witness, frame_ids=[],
                                              native_occurrences=occurrences, surviving_occurrences=remaining))
            diagnostic['frame_ids'].append(frame['frame_id'])
            if not remaining:
                exhausted.append(witness)
        if exhausted:
            blocked[frame['frame_id']] = exhausted
    already = {c['payload_id'] for c in base['withheld_candidates']}
    frame_blocks = set(base['blocked_frames']) | set(blocked)
    available, withheld, decisions = [], [], []
    for candidate in base['raw_view']['candidates']:
        surviving = [f for f in candidate['frame_ids'] if f not in frame_blocks]
        suspend = candidate['payload_id'] in already or not surviving
        decisions.append(dict(payload_id=candidate['payload_id'], surviving_frame_ids=surviving,
                              witness_blocked_frame_ids=[f for f in candidate['frame_ids'] if f in blocked],
                              prior_policy_withheld=candidate['payload_id'] in already, withheld=suspend))
        (withheld if suspend else available).append(candidate)
    base.update(witness_feedback=evidence, rejected_occurrences=rejected,
                witness_blocked_frames=blocked, witness_support=list(diagnostics.values()), witness_decisions=decisions,
                available_candidates=available, withheld_candidates=withheld, candidate_filter_used=bool(withheld))
    return base


SCENARIOS = ('reject_extra_witness', 'reject_correct_witness', 'alternate_witnesses',
             'other_occurrence', 'hidden_reference_twin', 'shared_required_witness')


def fixture(name, seed, renamed):
    source_case = ('wrong_feedback' if name == 'reject_correct_witness' else
                   'hidden_reference_twin' if name == 'hidden_reference_twin' else 'extra_route')
    rows, region, source, query, expected = make_fixture(source_case, seed, False)
    if name in ('alternate_witnesses', 'shared_required_witness'):
        for i, (body, kind) in enumerate((('Qual é a cor do dore?', 'user_turn'),
                                         ('A cor do bore é âmbar.', 'user_turn'),
                                         ('Intervalo observado.', 'assistant_generated'))):
            rows.append(dict(hierarchy_id=region, source_id='fourth-demo-' + str(i),
                             sequence=max(r['sequence'] for r in rows) + 1, text=body, source_kind=kind))
    if name == 'other_occurrence':
        index = next(i for i, r in enumerate(rows) if r['source_id'] == 'added-map-0-a')
        copies = [dict(r, source_id=r['source_id'] + '-repeat') for r in rows[index - 1:index + 1]]
        rows[index + 1:index + 1] = copies
        rows = [dict(r, sequence=i + 1) for i, r in enumerate(rows)]
    if renamed:
        symbols = sorted({c for r in rows for c in r['text']} | set(source + query))
        alphabet = list(ascii_lowercase + digits + ''.join(chr(i) for i in range(0xe0, 0x100) if i != 0xf7))
        if len(symbols) > len(alphabet):
            raise ValueError('injective fixture alphabet exhausted')
        Random(seed).shuffle(alphabet)
        mapping = dict(zip(symbols, alphabet))
        convert = lambda s: ''.join(mapping[c] for c in s)
        rows = [dict(r, text=convert(r['text'])) for r in rows]
        source, query = convert(source), convert(query)
        expected = [convert(s) for s in expected]
    return rows, region, source, query, expected


def choose(native, region, source, *, repeated=False, source_id=None, coverage=None):
    rows = collect(native, [region])
    view = witness_read(native, region, source, enabled=True)['raw_view']
    candidate = next((c for c in view['candidates'] if any(o[1] == 'added-map-target' for o in c['origins'])), view['candidates'][0])
    frames = [f for f in view['frames'] if f['frame_id'] in candidate['frame_ids']]
    support = witness_occurrence_map(rows, region)
    choices = [(f, w, support[canonical(w)]) for f in frames for w in f['witnesses']]
    if source_id is not None:
        choices = [item for item in choices if any(p['source']['source_id'] == source_id for p in item[2])]
    if coverage is not None:
        def shared(item):
            return all(canonical(item[1]) in {canonical(w) for w in f['witnesses']} for f in frames)
        choices = [item for item in choices if shared(item) == (coverage == 'SHARED')]
    if not choices:
        raise ValueError('scripted source address not in candidate evidence')
    choices.sort(key=lambda item: (item[2][0]['source']['sequence'], item[2][0]['target']['sequence'], item[0]['frame_id']))
    frame, witness, occurrences = (max(choices, key=lambda item: len(item[2])) if repeated else choices[0])
    binding = receipt(native, region, source, candidate['payload_id'])
    return binding, witness_request(frame['frame_id'], witness, occurrences[0])


def scenario(library, name, seed, renamed):
    rows, region, source, query, expected = fixture(name, seed, renamed)
    with tempfile.TemporaryDirectory(prefix='memoria-witness-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            persist(native, rows)
            before = witness_read(native, region, query, enabled=True)
            coverage = ('ALTERNATIVE' if name == 'alternate_witnesses' else
                        'SHARED' if name == 'shared_required_witness' else None)
            binding, target = choose(native, region, source, repeated=name == 'other_occurrence', coverage=coverage)
            first = record_addressed(native, binding, 'witness-1', 'scripted-caller', 'oppose', target)
            after = witness_read(native, region, query, enabled=True)
            log = operations(native, region)
            checks = dict(raw_unchanged=before['raw_view'] == after['raw_view'],
                          read_only=collect(native, [region]) == rows and operations(native, region) == log,
                          exact_native_pair=first['event']['target']['occurrence']['source']['source_id'] == target['source_address'][1]
                                            and first['event']['target']['occurrence']['target']['source_id'] == target['target_address'][1],
                          exactly_one_occurrence_rejected=len(after['rejected_occurrences']) == 1,
                          retained_source_rows=all(r in collect(native, [region]) for r in first['event']['target']['occurrence'].values()),
                          replay_no_append=record_addressed(native, binding, 'witness-1', 'scripted-caller', 'oppose', target)['status'] == 'EXACT_REPLAY'
                                           and operations(native, region) == log,
                          disabled_preserves_raw=witness_read(native, region, query)['available_candidates'] == before['available_candidates'],
                          unqualified=after['answer'] is None and not after['qualified'] and not after['selection_used'])
            try:
                addressed_read(native, region, query, enabled=True)
            except ValueError:
                checks['older_reader_refuses_unsupported_active_controls'] = True
            else:
                checks['older_reader_refuses_unsupported_active_controls'] = False
            native.reopen()
            checks['cold_full_view_equal'] = witness_read(native, region, query, enabled=True) == after
            withdraw_addressed(native, region, 'undo-witness', 'scripted-caller', 'witness-1')
            restored = witness_read(native, region, query, enabled=True)
            checks['withdrawal_restores'] = restored['available_candidates'] == before['available_candidates']
            checks['feedback_history_preserved'] = operations(native, region)[0] == {k: first[k] for k in ('event', 'address')}
            native.reopen()
            checks['withdrawal_cold_equal'] = witness_read(native, region, query, enabled=True) == restored
            return dict(scenario=name, renamed=renamed, rows=rows, source_query=source, heldout_query=query,
                        expected=expected, binding=binding, requested_target=target, after=after, checks=checks,
                        before_score=score([c['text'] for c in before['available_candidates']], expected),
                        after_score=score([c['text'] for c in after['available_candidates']], expected))
        finally:
            native.close()


def probe(library, seed):
    cases = [scenario(library, n, seed, r) for r in (False, True) for n in SCENARIOS]
    checks = {f'{i}:{k}': v for i, c in enumerate(cases) for k, v in c['checks'].items()}
    for i, name in enumerate(SCENARIOS):
        checks['rename:' + name] = all(cases[i][k] == cases[i + len(SCENARIOS)][k] for k in ('before_score', 'after_score'))
    for offset in (0, len(SCENARIOS)):
        positive, twin = cases[offset], cases[offset + 4]
        checks[f'twin_inputs:{offset}'] = positive['rows'] == twin['rows'] and positive['binding'] == twin['binding']
        checks[f'twin_reads:{offset}'] = positive['after'] == twin['after']
    return dict(format='memoria.ia-witness-feedback-probe-v1', seed=seed, cases=cases, checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL', integrity_passed=sum(checks.values()), integrity_total=len(checks),
                effects={c['scenario']: {k: c[k] for k in ('before_score', 'after_score')} for c in cases if not c['renamed']},
                general_learning_status='NOT_ESTABLISHED', factual_quality_status='NOT_EVALUATED',
                limitation='Caller rejection of one exact native adjacent pair; a frame is masked only when a required '
                'witness has no surviving occurrence. Wrong rejection still loses content; alternate frames/occurrences '
                'can retain errors. No deletion, adjacency rewrite, factual judgment or scale claim.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20270113)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.library, args.seed)
    result['report_content_sha256'] = fingerprint(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical(result) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('seed', 'integrity_status', 'integrity_passed', 'integrity_total', 'effects', 'report_content_sha256')}))
    raise SystemExit(0 if result['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
