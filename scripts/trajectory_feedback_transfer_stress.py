#!/usr/bin/env python3
"""Held-out symbolic workload: feedback quality and redundant route support.

No evaluator reference enters recording, retrieval or target selection.
"""
import argparse
import gzip
import json
from pathlib import Path
from random import Random
import tempfile

from mobile_region_replay import NativeProbe
from trajectory_addressed_feedback_probe import operations, record_addressed, receipt, withdraw_addressed, witness_occurrence_map
from trajectory_feedback_ledger_probe import canonical
from trajectory_question_frame_probe import collect, persist, score
from trajectory_region_evidence_probe import fingerprint
from trajectory_witness_feedback_probe import witness_read, witness_request


POLICIES = ('CONTENT', 'FRAME', 'WITNESS')
FEEDBACK = ('reject_extra', 'reject_expected')
FAMILIES = ('brackets', 'delimited')
REGIMES = ('minimal', 'extra_redundant', 'both_redundant')


def workload(seed, family, regime):
    if family not in FAMILIES or regime not in REGIMES:
        raise ValueError('unknown symbolic family or support regime')
    rng = Random(seed)
    symbols = rng.sample('abcdefghijklmno', 4)
    targets = rng.sample('pqrstuvwxyz', 4)
    mapping = dict(zip(symbols, targets))
    convert = lambda s: ''.join(mapping[c] for c in s)
    if family == 'brackets':
        question = lambda s: 'Q[' + s + ']?'
        content = lambda s, v: 'R[' + s + ']=' + v + '.'
    else:
        question = lambda s: '?(' + s + ')::'
        content = lambda s, v: '$(' + s + ') -> ' + v + '!'
    region = f'conversation:transfer-stress:{seed}:{family}:{regime}'
    rows = []
    def add(text, source, kind='user_turn'):
        rows.append(dict(hierarchy_id=region, source_id=source, sequence=len(rows) + 1,
                         text=text, source_kind=kind))
    examples = [symbols[i] + symbols[i + 1] for i in range(3)]
    for route in ('copy', 'transform'):
        redundant = regime == 'both_redundant' or (regime == 'extra_redundant' and route == 'transform')
        demos = examples + ([symbols[3] + symbols[0]] if redundant else [])
        for i, subject in enumerate(demos):
            add(question(subject), f'{route}-{i}-q')
            add(content(subject if route == 'copy' else convert(subject), str(i + 1)), f'{route}-{i}-a')
            add('GAP', f'{route}-{i}-barrier', 'assistant_generated')
    subjects = [symbols[0] + symbols[3], symbols[0] + symbols[2],
                symbols[1] + symbols[3], symbols[2] + symbols[0]]
    queries = []
    for i, subject in enumerate(subjects):
        expected, extra = content(subject, str(i + 5)), content(convert(subject), str(i + 5))
        add(expected, 'expected-anchor' if i == 0 else f'expected-heldout-{i}')
        add('GAP', f'expected-{i}-barrier', 'assistant_generated')
        add(extra, 'extra-anchor' if i == 0 else f'extra-heldout-{i}')
        add('GAP', f'extra-{i}-barrier', 'assistant_generated')
        queries.append(dict(name='anchor' if i == 0 else f'heldout-{i}', text=question(subject),
                            role='anchor' if i == 0 else 'heldout', expected=[expected], opposite_reference=[extra]))
    unseen = next(c for c in 'abcdefghijklmnopqrstuvwxyz' if c not in symbols + targets)
    for name, subject in (('absent_known_symbols', symbols[0] * 2), ('unseen_symbol', symbols[0] + unseen)):
        queries.append(dict(name=name, text=question(subject), role='absence', expected=[], opposite_reference=[]))
    return rows, region, queries


def scripted_feedback(native, region, anchor_query, policy, action):
    """Caller operation selected by native origin IDs, not evaluation references."""
    if policy not in POLICIES or action not in FEEDBACK:
        raise ValueError('invalid scripted operation')
    view = witness_read(native, region, anchor_query, enabled=True)['raw_view']
    source = 'extra-anchor' if action == 'reject_extra' else 'expected-anchor'
    candidate = next(c for c in view['candidates'] if any(o[1] == source for o in c['origins']))
    binding = receipt(native, region, anchor_query, candidate['payload_id'])
    target = dict(kind=policy)
    if policy in ('FRAME', 'WITNESS'):
        frame = next(f for f in view['frames'] if f['frame_id'] == candidate['frame_ids'][0])
        target['frame_id'] = frame['frame_id']
        if policy == 'WITNESS':
            support = witness_occurrence_map(collect(native, [region]), region)
            choices = [(w, p) for w in frame['witnesses'] for p in support[canonical(w)]]
            witness, pair = min(choices, key=lambda item: (item[1]['source']['sequence'], item[1]['target']['sequence']))
            target = witness_request(frame['frame_id'], witness, pair)
    return record_addressed(native, binding, 'scripted-opposition', 'scripted-caller', 'oppose', target)


def trial(library, seed, family, regime, policy, action):
    rows, region, queries = workload(seed, family, regime)
    with tempfile.TemporaryDirectory(prefix='memoria-feedback-stress-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            persist(native, rows)
            before = {q['name']: witness_read(native, region, q['text'], enabled=True) for q in queries}
            operation = scripted_feedback(native, region, queries[0]['text'], policy, action)
            log = operations(native, region)
            after = {q['name']: witness_read(native, region, q['text'], enabled=True) for q in queries}
            checks = dict(learning_unchanged=collect(native, [region]) == rows,
                          reads_do_not_append=operations(native, region) == log,
                          raw_views_unchanged=all(before[q['name']]['raw_view'] == after[q['name']]['raw_view'] for q in queries),
                          only_anchor_addressed=all(operation['event']['receipt']['query'] != q['text'] for q in queries if q['role'] != 'anchor'),
                          queries_not_ingested=all(q['text'] not in {r['text'] for r in rows} for q in queries),
                          unqualified=all(v['answer'] is None and not v['qualified'] and not v['selection_used'] for v in after.values()),
                          absent_queries_stay_empty=all(not after[q['name']]['available_candidates'] for q in queries if q['role'] == 'absence'))
            native.reopen()
            checks['cold_full_views_equal'] = all(witness_read(native, region, q['text'], enabled=True) == after[q['name']] for q in queries)
            withdraw_addressed(native, region, 'undo-opposition', 'scripted-caller', 'scripted-opposition')
            restored = {q['name']: witness_read(native, region, q['text'], enabled=True) for q in queries}
            checks['withdrawal_restores_availability'] = all(restored[k]['available_candidates'] == before[k]['available_candidates'] for k in before)
            checks['original_feedback_preserved'] = operations(native, region)[0] == {k: operation[k] for k in ('address', 'event')}
            reads = []
            for q in queries:
                name = q['name']
                before_texts = [c['text'] for c in before[name]['available_candidates']]
                after_texts = [c['text'] for c in after[name]['available_candidates']]
                reads.append(dict(query=q, before=before[name], after=after[name],
                                  before_score=score(before_texts, q['expected']), after_score=score(after_texts, q['expected']),
                                  opposite_before_score=score(before_texts, q['opposite_reference']),
                                  opposite_after_score=score(after_texts, q['opposite_reference'])))
            return dict(family=family, regime=regime, policy=policy, scripted_action=action,
                        rows=rows, operation=operation, queries=reads, checks=checks)
        finally:
            native.close()


def summarize(cases):
    groups = {}
    for case in cases:
        key = f'{case["policy"]}:{case["scripted_action"]}:{case["regime"]}'
        group = groups.setdefault(key, dict(heldout_queries=0, before={k: 0 for k in ('true_positive', 'false_positive', 'false_negative')},
                                           after={k: 0 for k in ('true_positive', 'false_positive', 'false_negative')},
                                           exact_sets_before=0, exact_sets_after=0))
        for readout in case['queries']:
            if readout['query']['role'] != 'heldout':
                continue
            group['heldout_queries'] += 1
            for when in ('before', 'after'):
                scores = readout[when + '_score']
                group['exact_sets_' + when] += int(scores['exact_set'])
                for metric in group[when]:
                    group[when][metric] += scores[metric]
    return groups


def probe(library, seed):
    cases = [trial(library, seed, family, regime, policy, action)
             for family in FAMILIES for regime in REGIMES for policy in POLICIES for action in FEEDBACK]
    checks = {f'{i}:{k}': v for i, case in enumerate(cases) for k, v in case['checks'].items()}
    return dict(format='memoria.ia-feedback-transfer-stress-v1', seed=seed, cases=cases,
                checks=checks, integrity_status='PASS' if all(checks.values()) else 'FAIL',
                integrity_passed=sum(checks.values()), integrity_total=len(checks),
                query_occurrences=sum(len(c['queries']) for c in cases), heldout_summary=summarize(cases),
                factual_quality_status='NOT_EVALUATED', general_learning_status='NOT_ESTABLISHED',
                caller_reliability_estimated=False,
                limitation='Controlled correct/wrong caller operations, two formal templates and three support regimes. '
                'Held-out variables, not independent natural-language data. Opposite references reuse identical reads. '
                'No evaluator labels enter policy; no autonomous feedback-reliability estimator or weight update.')


def write_report(path, result):
    """Deterministic compression preserves every full query/evidence packet."""
    raw = (canonical(result) + '\n').encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as destination:
        with gzip.GzipFile(filename='', fileobj=destination, mode='wb', mtime=0) as archive:
            archive.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20270115)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.library, args.seed)
    result['report_content_sha256'] = fingerprint(result)
    write_report(args.output, result)
    print(json.dumps({k: result[k] for k in ('seed', 'integrity_status', 'integrity_passed', 'integrity_total', 'query_occurrences', 'heldout_summary', 'report_content_sha256')}))
    raise SystemExit(0 if result['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
