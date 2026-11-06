#!/usr/bin/env python3
"""Disabled-by-default transfer of opposition to an exact uniquely witnessed frame.

This tests credit assignment, not factual validation or semantic generalization.
"""
import argparse
import json
from pathlib import Path
from random import Random
from string import ascii_lowercase, digits
import tempfile

from mobile_region_replay import NativeProbe
from trajectory_feedback_ledger_probe import canonical, events, receipt, record
from trajectory_feedback_withdrawal_probe import (
    feedback_projection, withdrawals, withdrawal_read, withdrawal_region, withdraw,
)
from trajectory_question_frame_probe import collect, persist, score
from trajectory_region_evidence_probe import fingerprint
from trajectory_route_relation_probe import fixture, read


def witness_origins(view, frame):
    roots = {root for witness in frame['witnesses'] for root in witness[:2]}
    return {root: view['root_provenance'][root] for root in sorted(roots)}


def learn_penalties(rows, ledger):
    """Derive reversible binary frame penalties from persisted active opposition.

    A unique generating frame is an attribution assumption, not proof of fault.
    No language vocabulary, expected answer or target-query label is accepted.
    """
    prefixes = {fingerprint(rows[:size]): size for size in range(len(rows) + 1)}
    result = []
    for entry in ledger:
        event = entry['event']
        if event['stance'] != 'oppose':
            continue
        binding = event['receipt']
        item = dict(feedback=entry, eligible=False)
        result.append(item)
        size = prefixes.get(binding['snapshot_sha256'])
        if size is None:
            item['reason'] = 'HISTORICAL_PREFIX_UNAVAILABLE'
            continue
        historical = read(rows[:size], binding['region'], binding['query'])
        body = {k: v for k, v in binding.items() if k != 'receipt_id'}
        candidates = [c for c in historical['candidates']
                      if canonical(c) == canonical(binding['candidate'])]
        if (fingerprint(body) != binding['receipt_id'] or
                fingerprint(historical) != binding['view_sha256'] or len(candidates) != 1):
            item['reason'] = 'HISTORICAL_RECEIPT_NOT_REPRODUCIBLE'
            continue
        frame_ids = candidates[0]['frame_ids']
        if len(frame_ids) != 1:
            item['reason'] = 'AMBIGUOUS_FRAME_ATTRIBUTION'
            continue
        frame = next(f for f in historical['frames'] if f['frame_id'] == frame_ids[0])
        item.update(eligible=True, reason='UNIQUE_FRAME_ATTRIBUTION_ASSUMPTION',
                    frame=frame, witness_provenance=witness_origins(historical, frame),
                    historical_prefix_rows=size)
    return result


def route_feedback_read(native, region, query, *, enabled=False):
    withdrawal_region(region)
    base = withdrawal_read(native, region, query, enabled=enabled)
    base['format'] = 'memoria.ia-exact-frame-feedback-view-v1'
    base['route_transfer_enabled'] = enabled
    base['general_learning_status'] = 'NOT_ESTABLISHED'
    if not enabled:
        return base
    rows = collect(native, [region])
    projection = feedback_projection(events(native, region), withdrawals(native, region))
    active = [dict(address=e['address'], event=e['event']) for e in projection if e['active']]
    penalties = learn_penalties(rows, active)
    view = base['raw_view']
    frames = {f['frame_id']: f for f in view['frames']}
    blocked = {}
    for penalty in penalties:
        if not penalty['eligible']:
            continue
        frame = frames.get(penalty['frame']['frame_id'])
        if (frame is not None and canonical(frame) == canonical(penalty['frame']) and
                canonical(witness_origins(view, frame)) == canonical(penalty['witness_provenance'])):
            blocked.setdefault(frame['frame_id'], []).append(penalty['feedback'])
    decisions = []
    available, withheld = [], []
    local_withheld = {c['payload_id'] for c in base['withheld_candidates']}
    for candidate in view['candidates']:
        matched = [f for f in candidate['frame_ids'] if f in blocked]
        surviving = [f for f in candidate['frame_ids'] if f not in blocked]
        # A penalty cannot suppress a candidate still reached by another frame.
        route_withheld = bool(matched) and not surviving
        suspend = candidate['payload_id'] in local_withheld or route_withheld
        decisions.append(dict(payload_id=candidate['payload_id'], penalized_frame_ids=matched,
                              surviving_frame_ids=surviving, route_withheld=route_withheld,
                              local_withheld=candidate['payload_id'] in local_withheld,
                              withheld=suspend))
        (withheld if suspend else available).append(candidate)
    base.update(route_penalties=penalties, blocked_frames=blocked, route_decisions=decisions,
                available_candidates=available, withheld_candidates=withheld,
                candidate_filter_used=bool(withheld))
    return base


SCENARIOS = ('extra_route', 'wrong_feedback', 'ambiguous_attribution',
             'alternate_frame_survives', 'hidden_reference_twin')


def make_fixture(name, seed, renamed):
    rows, region, queries = fixture('partial_overlap' if name in ('extra_route', 'alternate_frame_survives', 'hidden_reference_twin')
                                    else 'same_root_two_routes', seed)
    source_query = next(q['text'] for q in queries if q['name'] ==
                        ('covered' if name == 'wrong_feedback' else 'literal_cue'))
    entity = 'ore' if name == 'alternate_frame_survives' else 'norde'
    heldout = ('QUAL É A COR DO NORDE?' if name == 'wrong_feedback' else f'Qual é a cor do {entity}?')
    raw_fact = f'A cor do {entity} é prata.'
    transformed = f'A cor do {entity.replace("n", "l").replace("d", "b")} é prata.'
    for index, body in enumerate(dict.fromkeys((raw_fact, transformed))):
        sequence = 1 + max(r['sequence'] for r in rows)
        rows += [dict(hierarchy_id=region, source_id=f'heldout-{index}', sequence=sequence,
                      text=body, source_kind='user_turn'),
                 dict(hierarchy_id=region, source_id=f'heldout-{index}-barrier', sequence=sequence + 1,
                      text='Intervalo observado.', source_kind='assistant_generated')]
    expected = [transformed] if name == 'hidden_reference_twin' else [raw_fact]
    if renamed:
        symbols = sorted({c for r in rows for c in r['text']} | set(source_query + heldout))
        alphabet = list(ascii_lowercase + digits + ''.join(chr(i) for i in range(0xe0, 0x100) if i != 0xf7))
        Random(seed).shuffle(alphabet)
        mapping = dict(zip(symbols, alphabet))
        convert = lambda s: ''.join(mapping[c] for c in s)
        rows = [dict(r, text=convert(r['text'])) for r in rows]
        source_query, heldout = convert(source_query), convert(heldout)
        expected = [convert(s) for s in expected]
    return rows, region, source_query, heldout, expected


def scenario(library, name, seed, renamed):
    rows, region, source_query, heldout, expected = make_fixture(name, seed, renamed)
    with tempfile.TemporaryDirectory(prefix='memoria-route-feedback-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            persist(native, rows)
            initial = route_feedback_read(native, region, heldout, enabled=True)
            source = route_feedback_read(native, region, source_query, enabled=True)
            target = (next(c for c in source['raw_view']['candidates']
                           if any(o[1] == 'added-map-target' for o in c['origins']))
                      if name in ('extra_route', 'alternate_frame_survives', 'hidden_reference_twin') else source['raw_view']['candidates'][0])
            binding = receipt(native, region, source_query, target['payload_id'])
            record(native, binding, 'frame-opposition', 'scripted-caller', 'oppose')
            saved_rows, saved_ledger = collect(native, [region]), events(native, region)
            strict = withdrawal_read(native, region, heldout, enabled=True)
            transferred = route_feedback_read(native, region, heldout, enabled=True)
            disabled = route_feedback_read(native, region, heldout)
            checks = dict(different_query=heldout != source_query,
                          heldout_root_not_feedback_target=all(c['payload_id'] != target['payload_id'] for c in initial['raw_view']['candidates']),
                          raw_views_unchanged=initial['raw_view'] == strict['raw_view'] == transferred['raw_view'],
                          local_policy_no_transfer=strict['available_candidates'] == initial['available_candidates'],
                          disabled_no_filter=disabled['available_candidates'] == initial['raw_view']['candidates'],
                          read_only=collect(native, [region]) == saved_rows and events(native, region) == saved_ledger,
                          unqualified=transferred['answer'] is None and not transferred['qualified'] and not transferred['selection_used'])
            native.reopen()
            checks['cold_full_view_equal'] = route_feedback_read(native, region, heldout, enabled=True) == transferred
            withdraw(native, region, 'withdraw-frame-opposition', 'scripted-caller', saved_ledger[0])
            restored = route_feedback_read(native, region, heldout, enabled=True)
            checks['withdrawal_reverses_transfer'] = restored['available_candidates'] == initial['available_candidates']
            checks['ledger_preserved'] = events(native, region) == saved_ledger
            native.reopen()
            checks['withdrawal_cold_equal'] = route_feedback_read(native, region, heldout, enabled=True) == restored
            return dict(scenario=name, renamed=renamed, raw_rows=saved_rows,
                        source_query=source_query, heldout_query=heldout, binding=binding,
                        expected=expected, transferred=transferred, checks=checks,
                        raw_score=score([c['text'] for c in initial['available_candidates']], expected),
                        local_score=score([c['text'] for c in strict['available_candidates']], expected),
                        transferred_score=score([c['text'] for c in transferred['available_candidates']], expected))
        finally:
            native.close()


def probe(library, seed):
    cases = [scenario(library, name, seed, renamed) for renamed in (False, True) for name in SCENARIOS]
    checks = {f'{i}:{key}': value for i, case in enumerate(cases) for key, value in case['checks'].items()}
    for i, name in enumerate(SCENARIOS):
        checks['renaming:' + name] = all(cases[i][key] == cases[i + len(SCENARIOS)][key]
                                        for key in ('raw_score', 'local_score', 'transferred_score'))
    for offset in (0, len(SCENARIOS)):
        positive, twin = cases[offset], cases[offset + SCENARIOS.index('hidden_reference_twin')]
        checks[f'hidden_twin_inputs:{offset}'] = positive['raw_rows'] == twin['raw_rows'] and positive['binding'] == twin['binding']
        checks[f'hidden_twin_reads:{offset}'] = positive['transferred'] == twin['transferred']
    return dict(format='memoria.ia-route-feedback-probe-v1', seed=seed, cases=cases, checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                integrity_passed=sum(checks.values()), integrity_total=len(checks),
                effects={c['scenario']: {k: c[k] for k in ('raw_score', 'local_score', 'transferred_score')}
                         for c in cases if not c['renamed']},
                general_learning_status='NOT_ESTABLISHED', factual_quality_status='NOT_EVALUATED',
                limitation='Exact-frame binary policy transfer from unique attribution, not proof of route fault. '
                'Wrong feedback propagates; alternate frames survive; hidden-reference twins remain indistinguishable. '
                'Single-writer bounded replay; no default integration or numerical weight learning.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20270109)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = probe(args.library, args.seed)
    report['report_content_sha256'] = fingerprint(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical(report) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('seed', 'integrity_status', 'integrity_passed', 'integrity_total', 'effects', 'report_content_sha256')}))
    raise SystemExit(0 if report['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
