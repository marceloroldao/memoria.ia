import copy
import os
from pathlib import Path
import sys
import json
import subprocess

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_evidence_diagnosis import diagnose_evidence
from trajectory_feedback_session import FeedbackSession
from trajectory_transform_catalogue_probe import fixture_for
from trajectory_route_relation_probe import fixture as route_fixture


def codes(diagnosis):
    return {f['code'] for f in diagnosis['findings']}


@pytest.fixture
def session(tmp_path):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    with FeedbackSession(library,tmp_path) as active:
        yield active,library,tmp_path


def populate(active,fixture):
    for row in fixture['rows']:
        active.execute(dict(op='observe',scope=fixture['scope'],**row))
    return dict(scope=fixture['scope'],text=fixture['queries'][0]['text'])


@pytest.mark.parametrize('experiment,arm,expected',[
    ('unseen_identity','baseline','UNWITNESSED_SYMBOLS_IN_FRAMES'),
    ('conflicting_map','intervention','COMPETING_TRANSFORM_DESTINATIONS'),
    ('value_boundary','baseline','OBSERVED_TARGET_BOUNDARY_MISMATCH'),
    ('unseen_symbol','contrast','NO_OBSERVED_DESTINATION_IN_FRAMES'),
])
def test_native_diagnosis_reports_observed_gap_preserving_query_and_history(session,experiment,arm,expected):
    active,library,directory = session
    fixture = fixture_for('frequency',experiment,arm)
    request = populate(active,fixture)
    history = active.execute(dict(op='history',scope=fixture['scope']))
    query = active.execute(dict(op='query',**request))
    diagnosed = active.execute(dict(op='diagnose',**request))
    diagnosis = diagnosed['result']['diagnosis']
    assert expected in codes(diagnosis)
    plain = dict(diagnosed['result']);plain.pop('diagnosis')
    assert plain == query['result']
    assert active.execute(dict(op='history',scope=fixture['scope'])) == history
    active.close()
    with FeedbackSession(library,directory) as cold:
        assert cold.execute(dict(op='diagnose',**request)) == diagnosed


def test_empty_and_incompatible_frames_are_distinguished(session):
    active,_,_ = session
    empty = active.execute(dict(op='diagnose',text='Pergunta sem exemplos.'))['result']['diagnosis']
    assert codes(empty)=={'NO_LEARNED_FRAMES'} and empty['status']=='UNRESOLVED'
    fixture = fixture_for('frequency','unseen_symbol','baseline')
    request = populate(active,fixture)
    other = active.execute(dict(op='diagnose',scope=request['scope'],text='zzzzzzz'))['result']['diagnosis']
    assert 'NO_COMPATIBLE_SOURCE_FRAME' in codes(other)


def test_feedback_is_reported_as_feedback_not_missing_memory(session):
    active,_,_ = session
    fixture = fixture_for('frequency','unseen_identity','intervention')
    request = populate(active,fixture)
    query = active.execute(dict(op='query',**request))
    active.execute(dict(op='feedback',scope=fixture['scope'],receipt=query['result']['receipts'][0],
                        event_id='opposition',actor_id='operator',stance='oppose'))
    diagnosis = active.execute(dict(op='diagnose',**request))['result']['diagnosis']
    assert diagnosis['status']=='FEEDBACK_WITHHELD'
    assert diagnosis['raw_candidate_count']==diagnosis['withheld_candidate_count']==1
    assert diagnosis['available_candidate_count']==0
    assert 'EXPLICIT_FEEDBACK_WITHHOLDS_CANDIDATES' in codes(diagnosis)
    assert diagnosis['answer'] is None and diagnosis['selected_target'] is None
    assert not diagnosis['request_dispatched'] and not diagnosis['learning_performed']


def test_diagnosis_uses_no_evaluator_references_and_is_read_only(session):
    active,_,_ = session
    fixture = fixture_for('frequency','conflicting_map','intervention')
    request = populate(active,fixture)
    reading = active.execute(dict(op='query',**request))['result']
    region = active.execute(dict(op='history',scope=fixture['scope']))['result']['entries']
    before = copy.deepcopy(reading)
    diagnosis = diagnose_evidence(reading,region,request['text'])
    assert reading==before
    assert diagnosis['raw_candidate_count']==2 and not diagnosis['selection_used']
    corrupted = copy.deepcopy(reading)
    corrupted['raw_view']['candidates']=[]
    with pytest.raises(RuntimeError,match='disagrees'):
        diagnose_evidence(corrupted,region,request['text'])


def test_diagnosis_preserves_literal_and_transform_route_union(session):
    active,_,_ = session
    rows,_,queries = route_fixture('same_root_two_routes',20270107)
    for row in rows:
        active.execute(dict(op='observe',event_id=row['source_id'],text=row['text'],source_kind=row['source_kind']))
    text = next(q['text'] for q in queries if q['name']=='literal_cue')
    query = active.execute(dict(op='query',text=text))['result']
    assert any(e['route']=='literal_copy' for c in query['raw_view']['candidates'] for e in c['route_evidence'])
    diagnosed = active.execute(dict(op='diagnose',text=text))['result']
    diagnosis = diagnosed.pop('diagnosis')
    assert diagnosed==query and diagnosis['transform_trace']['candidate_set_equal']


def test_diagnose_terminal_protocol_preserves_empty_history(session,tmp_path):
    _,library,_ = session
    script = Path(__file__).resolve().parents[1]/'scripts'/'trajectory_feedback_session.py'
    commands = [dict(op='history'),dict(op='diagnose',text='Pergunta sem exemplos.'),dict(op='history')]
    run = subprocess.run([sys.executable,str(script),'--library',str(library.resolve()),'--data-dir',str(tmp_path/'cli')],
                         input=''.join(json.dumps(c)+'\n' for c in commands),text=True,capture_output=True,check=True)
    views = [json.loads(line) for line in run.stdout.splitlines()]
    assert len(views)==3 and views[0]==views[2]
    assert codes(views[1]['result']['diagnosis'])=={'NO_LEARNED_FRAMES'}
