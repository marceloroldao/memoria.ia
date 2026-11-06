#!/usr/bin/env python3
"""Opt-in feedback continuity with identical candidate evidence, never semantic transfer."""
import argparse
import json
from pathlib import Path
import tempfile

from mobile_region_replay import NativeProbe
from trajectory_feedback_gate_probe import gated_read
from trajectory_feedback_ledger_probe import canonical, events, ledger_region, receipt, record
from trajectory_question_frame_probe import collect, persist, score
from trajectory_region_evidence_probe import fingerprint
from trajectory_route_relation_probe import fixture, read


def evidence_identity(binding):
    return dict(region=binding['region'], query=binding['query'], candidate=binding['candidate'])


def witness_provenance(view, candidate):
    roots={candidate['payload_id']}
    roots.update(root for witness in candidate['witnesses'] for root in witness[:2])
    return {root:view['root_provenance'][root] for root in sorted(roots)}


def historical_proofs(rows, ledger):
    # Bounded laboratory replay of append-only projected prefixes, not a scalable index.
    prefixes={fingerprint(rows[:size]):size for size in range(len(rows)+1)}
    proofs={}
    for entry in ledger:
        binding=entry['event']['receipt']; key=binding['receipt_id']
        if key in proofs: continue
        size=prefixes.get(binding['snapshot_sha256'])
        if size is None: continue
        view=read(rows[:size],binding['region'],binding['query'])
        if fingerprint(view)!=binding['view_sha256']: continue
        candidate=next((c for c in view['candidates'] if canonical(c)==canonical(binding['candidate'])),None)
        if candidate is None: continue
        proofs[key]=dict(prefix_rows=size,view_sha256=binding['view_sha256'],
                         witness_provenance=witness_provenance(view,candidate))
    return proofs


def continuity_decision(binding, ledger, *, current_provenance=None, proofs=None):
    identity = canonical(evidence_identity(binding))
    matched = []
    for entry in ledger:
        previous = entry['event']['receipt']
        if previous['format'] != binding['format'] or canonical(evidence_identity(previous)) != identity:
            continue
        exact=canonical(previous)==canonical(binding)
        proof=(proofs or {}).get(previous['receipt_id'])
        if not exact and (current_provenance is None or proof is None or
                          canonical(proof['witness_provenance'])!=canonical(current_provenance)):
            continue
        matched.append(dict(entry, match_kind='EXACT_RECEIPT' if exact else 'IDENTICAL_CANDIDATE_EVIDENCE',
                            historical_proof=proof))
    stances = {entry['event']['stance'] for entry in matched}
    status = ('DISPUTED' if stances=={'support','oppose'} else 'OPPOSED' if 'oppose' in stances
              else 'SUPPORTED' if 'support' in stances else 'NO_FEEDBACK')
    return dict(receipt_id=binding['receipt_id'], evidence_identity_sha256=fingerprint(evidence_identity(binding)),
                status=status, withheld='oppose' in stances, feedback=matched,
                carried_event_count=sum(e['match_kind']=='IDENTICAL_CANDIDATE_EVIDENCE' for e in matched),
                current_witness_provenance=current_provenance,
                factual_quality_status='NOT_EVALUATED', semantic_context_status='NOT_EVALUATED')


def continuity_read(native, region, query, *, enabled=False):
    """Single-writer experiment. All raw candidate evidence must remain identical."""
    ledger_region(region)
    result = gated_read(native, region, query)  # Strict gate stays disabled here and unchanged.
    result['format'] = 'memoria.ia-evidence-continuity-gate-v1'
    if not enabled:
        return result
    ledger = events(native, region)
    proofs = historical_proofs(collect(native,[region]),ledger)
    available, withheld, decisions = [], [], []
    for candidate in result['raw_view']['candidates']:
        binding = receipt(native, region, query, candidate['payload_id'])
        item = continuity_decision(binding, ledger,
                    current_provenance=witness_provenance(result['raw_view'],candidate),proofs=proofs)
        decisions.append(dict(payload_id=candidate['payload_id'], **item))
        (withheld if item['withheld'] else available).append(candidate)
    result.update(enabled=True, decisions=decisions, available_candidates=available,
                  withheld_candidates=withheld, candidate_filter_used=bool(withheld))
    return result


SCENARIOS = ('unrelated_user', 'generated_barrier', 'repeated_target',
             'new_candidate', 'wrong_veto', 'hidden_context_twin')


def scenario(native, name, seed, renamed):
    case = 'same_root_two_routes' if name=='wrong_veto' else 'partial_overlap'
    rows, region, queries = fixture(case, seed, renamed)
    persist(native, rows)
    query = next(q for q in queries if q['name']=='literal_cue')
    before = continuity_read(native, region, query['text'], enabled=True)
    target = (before['raw_view']['candidates'][0] if name=='wrong_veto' else
              next(c for c in before['raw_view']['candidates'] if any(o[1]=='added-map-target' for o in c['origins'])))
    binding = receipt(native, region, query['text'], target['payload_id'])
    record(native, binding, 'opposition-1', 'caller-a', 'oppose')
    initial = continuity_read(native, region, query['text'], enabled=True)
    controls = {q['name']:continuity_read(native, region, q['text'], enabled=True)
                for q in queries if q['name']!='literal_cue'}
    stored = collect(native, [region])
    text = target['text'] if name=='repeated_target' else (target['text'][:-1]+'Z'+target['text'][-1] if name=='new_candidate'
                                                        else 'Observação posterior.')
    append = dict(hierarchy_id=region, source_id='continuity-append', sequence=max(r['sequence'] for r in stored)+1,
                  text=text, source_kind='assistant_generated' if name=='generated_barrier' else 'user_turn')
    persist(native, [append])
    after_rows = collect(native, [region]); ledger = events(native, region)
    after = continuity_read(native, region, query['text'], enabled=True)
    strict = gated_read(native, region, query['text'], enabled=True)
    target_after = next(c for c in after['raw_view']['candidates'] if c['payload_id']==target['payload_id'])
    current = receipt(native, region, query['text'], target['payload_id'])
    should_carry = name!='repeated_target'
    checks = dict(snapshot_changed=current['snapshot_sha256']!=binding['snapshot_sha256'],
                  exact_receipt_changed=current['receipt_id']!=binding['receipt_id'],
                  complete_candidate_equality=(canonical(current['candidate'])==canonical(binding['candidate']))==should_carry,
                  carry_only_if_evidence_identical=(target_after in after['withheld_candidates'])==should_carry,
                  strict_gate_expires=not strict['withheld_candidates'],
                  raw_view_equals_strict=after['raw_view']==strict['raw_view'],
                  queries_read_only=collect(native,[region])==after_rows and events(native,region)==ledger,
                  prefix_preserved=after_rows[:len(stored)]==stored,
                  target_retained_in_raw=target_after in after['raw_view']['candidates'],
                  default_disabled=continuity_read(native,region,query['text'])['available_candidates']==after['raw_view']['candidates'],
                  envelopes_unqualified=all(v['answer'] is None and not v['qualified'] and not v['selection_used'] and v['proposal_payload_id'] is None for v in (initial,after,strict)))
    # Only scenarios with unrelated/barrier appends claim unchanged other raw retrievals.
    if name in ('unrelated_user','generated_barrier','wrong_veto','hidden_context_twin'):
        def unchanged_control(q):
            current=continuity_read(native,region,q['text'],enabled=True)
            previous=controls[q['name']]
            return (all(current[k]==previous[k] for k in ('raw_view','available_candidates','withheld_candidates'))
                    and [d['status'] for d in current['decisions']]==[d['status'] for d in previous['decisions']])
        # Current receipt IDs legitimately change with the snapshot even with no feedback.
        checks['other_queries_unchanged'] = all(unchanged_control(q) for q in queries if q['name']!='literal_cue')
    else:
        checks['other_queries_no_feedback'] = all(not continuity_read(native,region,q['text'],enabled=True)['withheld_candidates']
                                                 for q in queries if q['name']!='literal_cue')
    if name=='new_candidate':
        checks['new_origin_not_vetoed'] = any(any(o[1]=='continuity-append' for o in c['origins']) for c in after['available_candidates'])
    if name=='repeated_target':
        checks['root_same_origins_changed'] = target_after['payload_id']==target['payload_id'] and len(target_after['origins'])==len(target['origins'])+1
    native.reopen()
    checks['cold_full_gate_equal'] = continuity_read(native,region,query['text'],enabled=True)==after
    checks['cold_rows_and_ledger_equal'] = collect(native,[region])==after_rows and events(native,region)==ledger
    # Hidden relevance changes only the evaluator, after operations. Observations/feedback are identical.
    expected = [target['text']] if name=='hidden_context_twin' else query['expected']
    return dict(scenario=name, renamed=renamed, raw_rows=stored, appended_row=append,
                initial_binding=binding, query=query['text'], expected=expected,
                before_raw_sha256=fingerprint(before['raw_view']),
                before_candidates=before['raw_view']['candidates'], after=after,
                strict_after_available_roots=[c['payload_id'] for c in strict['available_candidates']],
                before_score=score([c['text'] for c in before['available_candidates']],expected),
                strict_after_score=score([c['text'] for c in strict['available_candidates']],expected),
                continuity_after_score=score([c['text'] for c in after['available_candidates']],expected), checks=checks)


def probe(library, seed):
    cases = []
    for renamed in (False,True):
        for name in SCENARIOS:
            with tempfile.TemporaryDirectory(prefix='memoria-feedback-continuity-') as directory:
                native = NativeProbe(library,Path(directory))
                try: cases.append(scenario(native,name,seed,renamed))
                finally: native.close()
    checks = {f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    for renamed in (False,True):
        positive = next(c for c in cases if c['scenario']=='unrelated_user' and c['renamed']==renamed)
        twin = next(c for c in cases if c['scenario']=='hidden_context_twin' and c['renamed']==renamed)
        checks[f'hidden_twin:{renamed}'] = (positive['raw_rows']==twin['raw_rows'] and positive['appended_row']==twin['appended_row']
            and positive['initial_binding']==twin['initial_binding'] and positive['after']==twin['after'] and positive['expected']!=twin['expected'])
    effects = {c['scenario']:{key:c[key] for key in ('before_score','strict_after_score','continuity_after_score')}
               for c in cases if not c['renamed']}
    checks['renamed_score_parity'] = all(all(c[k]==effects[c['scenario']][k] for k in effects[c['scenario']]) for c in cases)
    return dict(format='memoria.ia-feedback-continuity-probe-v1',seed=seed,cases=cases,effects=effects,
                checks=checks,integrity_status='PASS' if all(checks.values()) else 'FAIL',
                integrity_passed=sum(checks.values()),integrity_total=len(checks),
                general_learning_status='NOT_ESTABLISHED',semantic_context_status='FAIL_INDISTINGUISHABLE_INPUTS',
                factual_quality_status='NOT_EVALUATED',
                limitation='Single-writer opt-in reuse of historical feedback only for identical query/scope/full candidate evidence. Wrong veto persists, repeated origins expire it, new candidates inherit nothing, and hidden relevance changes remain indistinguishable. No structural route learning or semantic correction guarantee.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=20270105)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(); report=probe(args.library,args.seed)
    report['report_content_sha256']=fingerprint(report)
    body=json.dumps(report,ensure_ascii=False,separators=(',',':'))+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(body,encoding='utf-8')
    print(body,end='');raise SystemExit(0 if report['integrity_status']=='PASS' else 1)


if __name__=='__main__': main()
