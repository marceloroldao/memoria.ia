import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import trajectory_forecast_lab as forecast


@pytest.fixture
def library():
    path=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so')).resolve()
    if not path.exists():
        if 'MEMORIA_NATIVE_LIBRARY' in os.environ: pytest.fail('Explicit native BDR library is missing')
        pytest.skip('Native integration runs in pinned-BDR CI')
    return path


def observe(lab,tick,value,obs=None,**extra):
    return lab.execute(dict(op='observe',observation_id=obs or f'm{tick}',entity='ab',tick=tick,value=value,**extra))['result']


def predict(lab,tick,prediction=None,**extra):
    return lab.execute(dict(op='predict',prediction_id=prediction or f'p{tick}',entity='ab',target_tick=tick,**extra))['result']


def train(lab,**extra):
    for t in range(3): observe(lab,t,10+t,**extra)


def history(lab,**extra):
    return lab.execute(dict(op='history',**extra))['result']


def test_automatic_loop_preserves_first_error_then_selects_recent_rule_after_reopen(library,tmp_path):
    with forecast.open_lab(library,tmp_path) as lab:
        train(lab)
        for tick,value in ((3,17),(4,18),(5,19),(6,20),(7,21)):
            result=predict(lab,tick)
            assert result['prediction']['comparison']=='PENDING'
            observed=observe(lab,tick,value)
            assert len(observed['comparisons'])==1
        saved=history(lab)
        summaries={p['prediction_id']:p for p in saved['predictions']}
        assert summaries['p3']['comparison']=='DIFFERS_FROM_SELECTED_PROPOSAL'
        assert summaries['p7']['selected_rule']=='recent_suffix'
        assert summaries['p7']['comparison']=='MATCHES_SELECTED_PROPOSAL'
        assert len(saved['entries'])==8
        assert len([e for e in saved['journal'] if e['event']['op']=='FORECAST'])==15
        assert len([e for e in saved['journal'] if e['event']['op']=='OUTCOME'])==15
        assert saved['repair_prediction_ids']==saved['repair_observation_ids']==[]
    with forecast.open_lab(library,tmp_path) as lab:
        assert history(lab)==saved
        before=history(lab)
        assert observe(lab,0,10)['status']=='EXACT_REPLAY'
        assert predict(lab,3)['status']=='EXACT_REPLAY'
        assert history(lab)==before
        for request in (dict(op='status'),dict(op='prediction',prediction_id='p3'),dict(op='history')):
            assert lab.execute(request)['qualified'] is False
            assert history(lab)==before


@pytest.mark.parametrize('command',[
    {'op':'unknown'},
    {'op':'observe','observation_id':'bad','entity':'ab','tick':0,'value':True},
    {'op':'observe','observation_id':'bad','entity':'ab','tick':0,'value':1.5},
    {'op':'observe','observation_id':'bad','entity':'ab','tick':0,'value':10001},
    {'op':'observe','observation_id':'bad','entity':'ab','tick':True,'value':1},
    {'op':'observe','observation_id':'bad','entity':'ab','tick':0,'value':1,'source_kind':'assistant_generated'},
    {'op':'predict','prediction_id':'bad','entity':'ab','target_tick':3,'expected':13},
    {'op':'predict','prediction_id':'bad','entity':'ab'},
    {'op':'status','scope':'../escape'},
])
def test_invalid_commands_rejected_before_any_native_write(library,tmp_path,command):
    with forecast.open_lab(library,tmp_path) as lab:
        before=history(lab)
        with pytest.raises(ValueError): lab.execute(command)
        assert history(lab)==before


def test_duplicate_content_and_reused_ids_cannot_inflate_support(library,tmp_path):
    with forecast.open_lab(library,tmp_path) as lab:
        train(lab);predict(lab,3);before=history(lab)
        for action in (lambda:observe(lab,2,12,'renamed'),lambda:observe(lab,2,99,'m2'),
                       lambda:predict(lab,3,'renamed'),lambda:predict(lab,4,'p3')):
            with pytest.raises(ValueError): action()
            assert history(lab)==before


def test_new_past_targets_and_decreasing_ticks_rejected_before_writes(library,tmp_path):
    with forecast.open_lab(library,tmp_path) as lab:
        train(lab);before=history(lab)
        with pytest.raises(ValueError,match='follow observed'): predict(lab,2)
        with pytest.raises(ValueError,match='must not decrease'): observe(lab,0,99,'late')
        assert history(lab)==before


def test_conflicting_same_tick_values_remain_divergent_and_do_not_rewrite_prediction(library,tmp_path):
    with forecast.open_lab(library,tmp_path) as lab:
        train(lab);predict(lab,3);observe(lab,3,13)
        result=observe(lab,3,99,'contradictory')
        assert result['comparisons'][0]['comparison']=='DIVERGENT_LATER_MEASUREMENTS'
        pending=predict(lab,4)['prediction']
        assert pending['proposal'] is None
        assert len(history(lab)['entries'])==5


def test_scope_isolation_and_unrelated_measurement_do_not_create_labels(library,tmp_path):
    with forecast.open_lab(library,tmp_path) as lab:
        train(lab,scope='a');predict(lab,3,scope='a')
        observe(lab,0,200,scope='b')
        assert lab.execute(dict(op='status',scope='b'))['result']['prediction_count']==0
        with pytest.raises(ValueError,match='not found'): lab.execute(dict(op='prediction',scope='b',prediction_id='p3'))
        assert lab.execute(dict(op='prediction',scope='a',prediction_id='p3'))['result']['prediction']['comparison']=='PENDING'
        response=lab.execute(dict(op='observe',scope='a',observation_id='other',entity='zz',tick=0,value=5))
        assert response['result']['comparisons']==[]
        assert len(history(lab,scope='a')['journal'])==3


def test_supplied_copy_stays_unqualified_and_no_world_worker_is_called(library,tmp_path,monkeypatch):
    def forbidden(*args): raise AssertionError('laboratory must consume supplied measurements only')
    monkeypatch.setattr(forecast.base,'measure',forbidden)
    with forecast.open_lab(library,tmp_path) as lab:
        train(lab);proposal=predict(lab,3)['prediction']['proposal']
        response=lab.execute(dict(op='observe',observation_id='copy',entity='ab',tick=3,value=proposal['value']))
        assert response['result']['comparisons'][0]['comparison']=='MATCHES_SELECTED_PROPOSAL'
        assert response['answer'] is None and response['qualified'] is False
        assert response['factual_quality_status']=='NOT_EVALUATED'


@pytest.mark.parametrize('exception',[ValueError,RuntimeError])
def test_partial_prediction_blocks_other_writes_and_same_id_recovers(library,tmp_path,monkeypatch,exception):
    with forecast.open_lab(library,tmp_path) as lab:
        train(lab);original=forecast.selection.recent.freeze
        def fail(*args,**kwargs): raise exception('injected second-stage failure')
        monkeypatch.setattr(forecast.selection.recent,'freeze',fail)
        with pytest.raises(RuntimeError,match='partially persisted'): predict(lab,3)
        status=lab.execute(dict(op='status'))['result']
        assert status['repair_prediction_ids']==['p3']
        before=history(lab)
        with pytest.raises(ValueError,match='incomplete prediction'): observe(lab,3,17)
        with pytest.raises(ValueError,match='incomplete prediction'): predict(lab,4)
        assert history(lab)==before
        monkeypatch.setattr(forecast.selection.recent,'freeze',original)
    with forecast.open_lab(library,tmp_path) as lab:
        assert predict(lab,3)['status']=='COMPLETED_RETRY'
        assert len(history(lab)['journal'])==3
        assert observe(lab,3,17)['comparisons'][0]['comparison']=='DIFFERS_FROM_SELECTED_PROPOSAL'


def test_failure_after_selector_commit_recovers_as_exact_replay(library,tmp_path,monkeypatch):
    with forecast.open_lab(library,tmp_path) as lab:
        train(lab);original=forecast.selection.freeze
        def fail_after(*args,**kwargs):
            original(*args,**kwargs)
            raise RuntimeError('injected response loss')
        monkeypatch.setattr(forecast.selection,'freeze',fail_after)
        with pytest.raises(RuntimeError,match='partially persisted'): predict(lab,3)
        assert lab.execute(dict(op='status'))['result']['repair_prediction_ids']==[]
        monkeypatch.setattr(forecast.selection,'freeze',original)
    with forecast.open_lab(library,tmp_path) as lab:
        assert predict(lab,3)['status']=='EXACT_REPLAY'
        assert len(history(lab)['journal'])==3


def test_partial_linkage_blocks_new_data_until_original_observation_replayed(library,tmp_path,monkeypatch):
    with forecast.open_lab(library,tmp_path) as lab:
        train(lab);predict(lab,3);original=forecast.selection.recent.link_measurement
        def fail(*args,**kwargs): raise RuntimeError('injected linkage failure')
        monkeypatch.setattr(forecast.selection.recent,'link_measurement',fail)
        with pytest.raises(RuntimeError,match='partially persisted'): observe(lab,3,17)
        assert lab.execute(dict(op='status'))['result']['repair_observation_ids']==['m3']
        before=history(lab)
        with pytest.raises(ValueError,match='incomplete observation'): observe(lab,4,18)
        with pytest.raises(ValueError,match='incomplete observation'): predict(lab,4)
        assert history(lab)==before
        monkeypatch.setattr(forecast.selection.recent,'link_measurement',original)
    with forecast.open_lab(library,tmp_path) as lab:
        assert observe(lab,3,17)['status']=='EXACT_REPLAY'
        saved=history(lab)
        assert len(saved['entries'])==4
        assert len([e for e in saved['journal'] if e['event']['op']=='OUTCOME'])==3
        assert saved['repair_observation_ids']==[]


def test_json_lines_validation_continues_but_partial_mutation_terminates_without_false_reply(library,tmp_path,monkeypatch):
    with forecast.open_lab(library,tmp_path) as lab:
        output=io.StringIO()
        forecast.serve(lab,io.StringIO('not json\n{"op":"status"}\n'),output)
        response=[json.loads(x) for x in output.getvalue().splitlines()]
        assert [r['ok'] for r in response]==[False,True]
        train(lab)
        def fail(*args,**kwargs): raise KeyError('injected internal failure after first native write')
        monkeypatch.setattr(forecast.selection.recent,'freeze',fail)
        output=io.StringIO()
        command=dict(op='predict',prediction_id='p3',entity='ab',target_tick=3)
        with pytest.raises(RuntimeError,match='partially persisted'):
            forecast.serve(lab,io.StringIO(json.dumps(command)+'\n{"op":"status"}\n'),output)
        assert output.getvalue()==''
        assert lab.execute(dict(op='status'))['result']['repair_prediction_ids']==['p3']


def test_oversized_model_preflight_rejects_before_starting_stages(library,tmp_path,monkeypatch):
    with forecast.open_lab(library,tmp_path) as lab:
        train(lab);before=history(lab);original=forecast.base.audit.metadata
        def reject(value):
            if isinstance(value,dict) and value.get('format')==forecast.base.FORMAT: raise ValueError('metadata too large')
            return original(value)
        monkeypatch.setattr(forecast.base.audit,'metadata',reject)
        with pytest.raises(ValueError,match='metadata too large'): predict(lab,3)
        assert history(lab)==before


def test_limits_keep_reads_and_exact_retries_available_with_maximum_identifiers(library,tmp_path):
    scope='s'*32
    with forecast.open_lab(library,tmp_path) as lab:
        for t in range(8):
            if t>=3: predict(lab,t,prediction='p'*39+str(t),scope=scope)
            observe(lab,t,10+t,obs='m'*39+str(t),scope=scope)
        before=history(lab,scope=scope)
        with pytest.raises(ValueError,match='observation limit'): observe(lab,8,18,scope=scope)
        with pytest.raises(ValueError,match='prediction limit'): predict(lab,8,scope=scope)
        assert predict(lab,3,prediction='p'*39+'3',scope=scope)['status']=='EXACT_REPLAY'
        assert observe(lab,0,10,obs='m'*39+'0',scope=scope)['status']=='EXACT_REPLAY'
        assert history(lab,scope=scope)==before


def test_same_advisory_lock_excludes_another_owner(library,tmp_path):
    with forecast.open_lab(library,tmp_path) as lab:
        observe(lab,0,10);before=history(lab)
        with pytest.raises(BlockingIOError):
            with forecast.open_lab(library,tmp_path): pass
        assert history(lab)==before


def test_foreign_raw_entry_blocks_writes_without_modifying_it(library,tmp_path):
    with forecast.open_lab(library,tmp_path) as lab:
        region='forecast-lab:principal'
        forecast.base.persist(lab.native,[dict(hierarchy_id=region,source_id='foreign',sequence=1,text='unrecognized',source_kind='user_turn')])
        before=forecast.base.collect(lab.native,[region])
        with pytest.raises(ValueError,match='foreign or malformed'): observe(lab,0,10)
        assert forecast.base.collect(lab.native,[region])==before


def test_example_runs_in_real_cli_and_reopens_in_another_process(library,tmp_path):
    root=Path(__file__).resolve().parents[1]
    command=[sys.executable,str(root/'scripts/trajectory_forecast_lab.py'),'--library',str(library),'--data-dir',str(tmp_path)]
    first=subprocess.run(command,input=(root/'examples/forecast-lab-session.jsonl').read_text(),
                         capture_output=True,text=True,cwd=root,check=True)
    outputs=[json.loads(line) for line in first.stdout.splitlines()]
    assert len(outputs)==16 and all(r['ok'] for r in outputs)
    assert outputs[-3]['result']['prediction']['comparison']=='DIFFERS_FROM_SELECTED_PROPOSAL'
    assert outputs[-2]['result']['prediction']['selected_rule']=='recent_suffix'
    assert outputs[-2]['result']['prediction']['comparison']=='MATCHES_SELECTED_PROPOSAL'
    second=subprocess.run(command,input='{"op":"prediction","prediction_id":"p3"}\n{"op":"prediction","prediction_id":"p7"}\n{"op":"status"}\n',
                          capture_output=True,text=True,cwd=root,check=True)
    assert [json.loads(line) for line in second.stdout.splitlines()]==outputs[-3:]
