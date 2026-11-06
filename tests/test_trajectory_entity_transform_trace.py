import copy
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_entity_transform_trace import fixture_for, probe, trace_transform


def test_interventions_use_new_entities_and_no_target_question_or_payload():
    for name in ('identity_pair','value_suffix'):
        _, baseline, _ = fixture_for(name,'baseline')
        targets = set(baseline['queries'][2]['expected'])
        target_questions = {q['text'] for q in baseline['queries'][:4]}
        for arm in ('targeted','contrast'):
            _, changed, _ = fixture_for(name,arm)
            assert changed['rows'][:len(baseline['rows'])] == baseline['rows']
            added = changed['rows'][len(baseline['rows']):]
            assert not targets.intersection(r['text'] for r in added)
            assert not target_questions.intersection(r['text'] for r in added)
            assert all(set(row) <= {'event_id','text','source_kind'} for row in added)


def test_trace_rejects_unwitnessed_identity_and_distinguishes_suffix_boundary():
    frame = dict(route='symbol_transform',frame_id='symbol_transform:test',witnesses=[],
                 source_prefix=[ord('Q')],source_suffix=[ord('?')],symbol_map=[[ord('A'),ord('a')]],
                 target_prefix=[ord('T')],target_bridge=[ord(':')],target_suffix=list(map(ord,' V.')))
    raw = dict(frames=[frame],candidates=[])
    view = dict(result=dict(raw_view=raw))
    saved = copy.deepcopy(view)
    missing = trace_transform(view,[], 'QF?')
    assert missing['frames'][0]['unwitnessed_symbols'] == [dict(symbol=ord('F'),text='F')]
    assert missing['frames'][0]['status'] == 'UNWITNESSED_QUERY_SYMBOLS'
    suffix = trace_transform(view,[dict(text='Ta:unknown.',source_kind='user_turn')], 'QA?')
    assert suffix['frames'][0]['target_checks'][0]['status'] == 'TARGET_SUFFIX_MISMATCH'
    assert view == saved


def test_native_interventions_isolate_identity_and_value_suffix():
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    report = probe(library)
    assert report['integrity_status'] == 'PASS' and all(report['checks'].values())
    summary = report['summary']
    assert summary['identity_pair']['baseline']['score']['recovered'] == 0
    assert summary['identity_pair']['targeted']['score']['recovered'] == 2
    assert summary['identity_pair']['contrast']['score']['recovered'] == 0
    assert summary['value_suffix']['baseline']['score']['recovered'] == 1
    assert summary['value_suffix']['targeted']['score']['recovered'] == 2
    assert summary['value_suffix']['contrast']['score']['recovered'] == 1
    for name in summary:
        assert summary[name]['baseline'] == summary[name]['irrelevant']
    for trial in report['trials']:
        assert all(c['score']['extra']==0 for c in trial['cases'][4:])
        assert trial['transform_trace']['candidate_set_equal']
    car = next(t for t in report['trials'] if t['experiment']=='identity_pair' and t['arm']=='targeted')
    assert any(dict(source=ord('F'),target=ord('F')) in frame.get('required_pairs',[]) and frame['status']=='ADMITTED_OBSERVED_ROOTS'
               for frame in car['transform_trace']['frames'])
