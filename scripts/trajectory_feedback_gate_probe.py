#!/usr/bin/env python3
"""Opt-in exact-receipt opposition veto; no learned route weights or truth labels."""
import argparse
import json
from pathlib import Path
import tempfile

from mobile_region_replay import NativeProbe
from trajectory_feedback_ledger_probe import canonical, events, ledger_region, receipt, record
from trajectory_question_frame_probe import collect, persist, score
from trajectory_region_evidence_probe import fingerprint
from trajectory_route_relation_probe import fixture, read


def decision(binding, ledger):
    matches = [entry for entry in ledger
               if canonical(entry['event']['receipt']) == canonical(binding)]
    stances = {entry['event']['stance'] for entry in matches}
    status = ('DISPUTED' if stances == {'support', 'oppose'} else
              'OPPOSED' if 'oppose' in stances else
              'SUPPORTED' if 'support' in stances else 'NO_FEEDBACK')
    return dict(receipt_id=binding['receipt_id'], status=status,
                withheld='oppose' in stances, feedback=matches,
                factual_quality_status='NOT_EVALUATED')


def gated_read(native, region, query, *, enabled=False):
    """Single-writer lab view. Available means not vetoed, never factually qualified."""
    ledger_region(region)  # Reject feedback hierarchies even while the gate is disabled.
    rows = collect(native, [region])
    raw = read(rows, region, query)
    ledger = events(native, region) if enabled else []
    decisions = []
    available, withheld = [], []
    for candidate in raw['candidates']:
        if enabled:
            binding = receipt(native, region, query, candidate['payload_id'])
            item = decision(binding, ledger)
        else:
            item = dict(status='DISABLED', withheld=False, feedback=[], receipt_id=None,
                        factual_quality_status='NOT_EVALUATED')
        decisions.append(dict(payload_id=candidate['payload_id'], **item))
        (withheld if item['withheld'] else available).append(candidate)
    return dict(format='memoria.ia-exact-feedback-gate-v1', enabled=enabled,
                raw_view=raw, decisions=decisions, available_candidates=available,
                withheld_candidates=withheld, candidate_filter_used=bool(withheld),
                answer=None, qualified=False, selected_target=None, selection_used=False,
                proposal_payload_id=None, factual_quality_status='NOT_EVALUATED')


SCENARIOS = ('correct_veto', 'wrong_veto', 'disputed_veto', 'wrong_support')


def scenario(native, name, seed, renamed=False):
    case = ('partial_overlap' if name in ('correct_veto', 'disputed_veto') else
            'same_root_two_routes' if name == 'wrong_veto' else 'wrong_transform')
    rows, region, queries = fixture(case, seed, renamed)
    persist(native, rows)
    query = next(q for q in queries if q['name'] == ('covered' if name == 'wrong_support' else 'literal_cue'))
    before_rows = collect(native, [region])
    before = gated_read(native, region, query['text'], enabled=True)
    # Operations target observed source addresses, never evaluator expected texts.
    candidates = before['raw_view']['candidates']
    target = (next(c for c in candidates if any(o[1] == 'added-map-target' for o in c['origins']))
              if case == 'partial_overlap' else candidates[0])
    binding = receipt(native, region, query['text'], target['payload_id'])
    controls = {q['name']:gated_read(native, region, q['text'], enabled=True)
                for q in queries if q['text'] != query['text']}
    first_stance = 'support' if name == 'wrong_support' else 'oppose'
    record(native, binding, 'feedback-1', 'caller-a', first_stance)
    if name == 'disputed_veto':
        for i in range(3):
            record(native, binding, f'support-{i}', 'caller-b', 'support')
    after = gated_read(native, region, query['text'], enabled=True)
    ledger = events(native, region)
    checks = dict(raw_rows_unchanged=collect(native, [region]) == before_rows,
                  raw_full_view_unchanged=after['raw_view'] == before['raw_view'],
                  other_queries_unchanged=all(gated_read(native, region, q['text'], enabled=True) == controls[q['name']]
                                              for q in queries if q['text'] != query['text']),
                  disabled_preserves_candidates=gated_read(native, region, query['text'])['available_candidates'] == candidates,
                  ledger_read_only=events(native, region) == ledger,
                  no_answer_qualification=after['answer'] is None and not after['qualified'] and not after['selection_used'],
                  target_retained_in_raw=target in after['raw_view']['candidates'],
                  exact_replay_no_effect=record(native, binding, 'feedback-1', 'caller-a', first_stance)['status'] == 'EXACT_REPLAY'
                                         and gated_read(native, region, query['text'], enabled=True) == after)
    expected_state = 'SUPPORTED' if name == 'wrong_support' else 'DISPUTED' if name == 'disputed_veto' else 'OPPOSED'
    target_decision = next(d for d in after['decisions'] if d['payload_id'] == target['payload_id'])
    checks['scripted_state'] = target_decision['status'] == expected_state
    checks['only_target_vetoed'] = ([c['payload_id'] for c in after['withheld_candidates']] ==
                                   ([] if name == 'wrong_support' else [target['payload_id']]))
    native.reopen()
    checks['cold_gate_equal'] = gated_read(native, region, query['text'], enabled=True) == after
    checks['cold_raw_equal'] = collect(native, [region]) == before_rows
    append = dict(hierarchy_id=region, source_id='later-context', sequence=max(r['sequence'] for r in before_rows)+1,
                  text='Observação posterior.', source_kind='user_turn')
    persist(native, [append])
    changed = gated_read(native, region, query['text'], enabled=True)
    checks['snapshot_veto_not_transferred'] = not changed['withheld_candidates'] and all(d['status'] == 'NO_FEEDBACK' for d in changed['decisions'])
    checks['historical_ledger_preserved'] = events(native, region) == ledger
    # Expected texts are consumed only here, after every read and feedback operation.
    before_score = score([c['text'] for c in before['available_candidates']], query['expected'])
    after_score = score([c['text'] for c in after['available_candidates']], query['expected'])
    return dict(scenario=name, renamed=renamed, raw_rows=before_rows, query=query,
                feedback_target_origin=target['origins'], before=before, after=after,
                after_append=changed, before_score=before_score, after_score=after_score,
                checks=checks)


def probe(library, seed):
    cases = []
    for renamed in (False, True):
        for name in SCENARIOS:
            with tempfile.TemporaryDirectory(prefix='memoria-feedback-gate-') as directory:
                native = NativeProbe(library, Path(directory))
                try:
                    cases.append(scenario(native, name, seed, renamed))
                finally:
                    native.close()
    checks = {f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    effects = {name:dict(before=next(c['before_score'] for c in cases if c['scenario']==name and not c['renamed']),
                         after=next(c['after_score'] for c in cases if c['scenario']==name and not c['renamed']))
               for name in SCENARIOS}
    checks['renamed_effect_parity'] = all(c['before_score'] == effects[c['scenario']]['before'] and
                                         c['after_score'] == effects[c['scenario']]['after'] for c in cases)
    return dict(format='memoria.ia-feedback-gate-probe-v1', seed=seed, cases=cases,
                effects=effects, checks=checks, integrity_status='PASS' if all(checks.values()) else 'FAIL',
                integrity_passed=sum(checks.values()), integrity_total=len(checks),
                general_learning_status='NOT_ESTABLISHED', factual_quality_status='NOT_EVALUATED',
                limitation='Explicit exact-receipt veto, opt-in single-writer lab. No route learning, factual vote, cross-query transfer or correction guarantee. Wrong opposition suppresses correct content; any snapshot append expires the veto.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20270103)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = probe(args.library, args.seed)
    report['report_content_sha256'] = fingerprint(report)
    body = json.dumps(report, ensure_ascii=False, separators=(',', ':')) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding='utf-8')
    print(body, end='')
    raise SystemExit(0 if report['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
