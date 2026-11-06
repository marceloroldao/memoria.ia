import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_surface_evaluation import ARMS, SURFACES, fixture
import trajectory_surface_evaluation as evaluation
from trajectory_transfer_evaluation import DOMAINS, SEEDS, trial


@pytest.mark.parametrize('domain',DOMAINS)
@pytest.mark.parametrize('seed',SEEDS)
def test_surface_conditions_keep_targets_and_evaluation_queries_out_of_demonstrations(domain,seed):
    for surface in SURFACES:
        baseline = fixture(domain,seed,surface,'baseline')
        prefix = baseline['rows']
        targets = {text for q in baseline['queries'] for text in q['expected']}
        questions = {q['text'] for q in baseline['queries']}
        for arm in ARMS:
            descriptor = fixture(domain,seed,surface,arm)
            assert descriptor['rows'][:len(prefix)] == prefix
            assert descriptor['queries'] == baseline['queries']
            added = descriptor['rows'][len(prefix):]+descriptor['foreign_rows']
            assert targets.isdisjoint(row['text'] for row in added)
            assert questions.isdisjoint(row['text'] for row in descriptor['rows']+descriptor['foreign_rows'])
            assert all(set(row)=={'text','event_id','source_kind'} for row in added)
            if arm=='generated': assert all(row['source_kind']=='assistant_generated' for row in added)
            if arm=='foreign': assert descriptor['rows']==prefix and len(descriptor['foreign_rows'])==9


@pytest.mark.parametrize('arm,status',[
    ('baseline','NO_COMPATIBLE_SOURCE_FRAME'),
    ('known_symbols_only','UNWITNESSED_SYMBOLS_IN_FRAMES'),
    ('wrong_map','NO_OBSERVED_DESTINATION_IN_FRAMES'),
    ('three_surface','OBSERVED_CANDIDATE_REQUIRES_REVIEW'),
])
def test_native_diagnosis_distinguishes_source_form_symbol_gap_and_target_mismatch(arm,status):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    report = trial(library,fixture('humidity',SEEDS[0],'uppercase',arm),operation='diagnose')
    assert all(report['checks'].values())
    for case in report['cases']:
        assert case['diagnosis']['transform_candidate_set_equal']
        assert case['answer'] is None and not case['qualified'] and not case['selection_used']
        if case['query']['family']=='surface': assert status in case['diagnosis']['findings']


def test_evaluator_cannot_be_used_to_execute_a_writing_operation():
    with pytest.raises(ValueError,match='read-only'):
        trial(Path('unused'),{},operation='observe')


def test_untaught_surface_failure_keeps_full_retrieval_gate_failed():
    cases = [dict(query=dict(family=family),score=dict(exact=passed),answer=None)
             for family,passed in (('surface',True),('original',True),('absence',True),('untaught_surface',False))]
    for case in cases: case['diagnosis'] = dict(transform_candidate_set_equal=True)
    report = evaluation.summarize([dict(fixture=dict(arm='three_surface'),cases=cases,checks=dict(read_only=True))])
    assert report['integrity_status']=='PASS' and report['retrieval_status']=='EXTRA_OR_MISSING_CONTENT'
    assert report['selected_answer_count']==0


def test_surface_strict_mode_rejects_retrieval_failure(tmp_path,monkeypatch):
    report = dict(integrity_status='PASS',retrieval_status='EXTRA_OR_MISSING_CONTENT',summary={})
    monkeypatch.setattr(evaluation,'probe',lambda library:dict(report))
    monkeypatch.setattr(sys,'argv',['probe','--library','unused','--output',str(tmp_path/'report.json'),'--strict-retrieval'])
    assert evaluation.main()==1
