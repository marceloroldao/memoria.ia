import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import trajectory_forecast_csv as importer

HEADER='observation_id,entity,tick,value\n'
DATA=HEADER+'m0,ab,0,10\nm1,ab,1,11\nm2,ab,2,12\nm3,ab,3,17\nm4,ab,4,18\nm5,ab,5,19\nm6,ab,6,20\nm7,ab,7,21\n'


def plan(text=DATA,scope='csv'):
    return importer.make_plan(importer.read_csv(io.StringIO(text)),scope)


def test_plan_forecasts_next_tick_without_inspecting_later_values_or_creating_backend():
    first=plan();second=plan(DATA.replace('m3,ab,3,17','m3,ab,3,99'))
    assert len(first['commands'])==13
    assert sum(c['command']['op']=='predict' for c in first['commands'])==5
    assert first['commands'][:4]==second['commands'][:4]
    assert first['commands'][3]['command']['target_tick']==3
    assert first['skipped_predictions'][-1]['reason']=='PREDICTION_BUDGET_REACHED'
    assert first['plan_sha256']!=second['plan_sha256']


@pytest.mark.parametrize('content',[
    '',HEADER,
    'observation_id,entity,tick,value,expected\nm0,ab,0,10,10\n',
    HEADER+'m0,ab,0,1.5\n',
    HEADER+'m0,ab,0,1e2\n',
    HEADER+'m0,ab,0,True\n',
    HEADER+'m0,ab,0,10001\n',
    HEADER+'m0,ab,1001,10\n',
    HEADER+'m0,ab,0\n',
    HEADER+'m0,ab,0,10,extra\n',
    HEADER+'m0,ab,0,10\nm0,ab,1,11\n',
    HEADER+'m0,ab,0,10\nm1,zz,1,11\n',
    HEADER+'m0,ab,1,10\nm1,ab,0,11\n',
    HEADER+'m0,ab,0,10\nm1,ab,0,11\n',
    DATA+'m8,ab,8,22\n',
])
def test_invalid_full_csv_rejected_by_preflight(content):
    with pytest.raises(ValueError): plan(content)


@pytest.mark.parametrize('delimiter',[',',';'])
def test_bom_whitespace_and_explicit_separator_are_normalized(delimiter):
    text='\ufeff'+(HEADER+' m0 , ab , 0 , 10 \n').replace(',',delimiter)
    data=importer.read_csv(io.StringIO(text),delimiter)
    assert data==[dict(observation_id='m0',entity='ab',tick=0,value=10)]


def test_sparse_ticks_use_next_integer_tick_not_next_future_csv_tick():
    value=plan(HEADER+'a,ab,0,1\nb,ab,2,2\nc,ab,4,3\nd,ab,8,5\n')
    targets=[c['command']['target_tick'] for c in value['commands'] if c['command']['op']=='predict']
    assert targets==[5,9]


def test_last_tick_reports_no_forecast_instead_of_late_failure_after_write():
    value=plan(HEADER+'a,ab,998,1\nb,ab,999,2\nc,ab,1000,3\n')
    assert value['skipped_predictions'][-1]['reason']=='TICK_LIMIT_REACHED'
    assert all(c['command']['op']=='observe' for c in value['commands'])


@pytest.fixture
def library():
    path=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so')).resolve()
    if not path.exists():
        if 'MEMORIA_NATIVE_LIBRARY' in os.environ: pytest.fail('Explicit native BDR library is missing')
        pytest.skip('Native integration runs in pinned-BDR CI')
    return path


def history(lab):
    return lab.execute(dict(op='history',scope='csv'))['result']


def run(lab,value=None):
    output=io.StringIO()
    result=importer.import_plan(lab,value or plan(),output)
    return result,[json.loads(line) for line in output.getvalue().splitlines()]


def test_full_import_replays_without_duplicates_and_preserves_first_error(library,tmp_path):
    with importer.forecast.open_lab(library,tmp_path) as lab:
        result,events=run(lab)
        assert result['status']['observation_count']==8 and result['status']['prediction_count']==5
        assert result['recovery_commands']==0 and len(events)==14
        saved=history(lab);by_id={p['prediction_id']:p for p in saved['predictions']}
        assert by_id[importer.automatic_id('csv','ab',3)]['comparison']=='DIFFERS_FROM_SELECTED_PROPOSAL'
        assert by_id[importer.automatic_id('csv','ab',7)]['comparison']=='MATCHES_SELECTED_PROPOSAL'
        assert by_id[importer.automatic_id('csv','ab',7)]['selected_rule']=='recent_suffix'
        assert all(e['qualified'] is False for e in events)
    with importer.forecast.open_lab(library,tmp_path) as lab:
        replay,events=run(lab)
        assert replay['status']==result['status']
        assert all(e['response']['result']['status']=='EXACT_REPLAY' for e in events[:-1])
        assert history(lab)==saved


def test_growing_csv_only_adds_new_suffix_and_keeps_frozen_forecast(library,tmp_path):
    records=plan()['records']
    with importer.forecast.open_lab(library,tmp_path) as lab:
        run(lab,importer.make_plan(records[:3]));first=history(lab)['journal']
        run(lab,importer.make_plan(records[:4]));middle=history(lab)
        assert middle['journal'][:len(first)]==first
        assert len(middle['entries'])==4 and len(middle['predictions'])==2
        run(lab);final=history(lab)
        assert final['journal'][:len(middle['journal'])]==middle['journal']
        assert len(final['entries'])==8


@pytest.mark.parametrize('change',['value','identity','shorter','edited_plan'])
def test_incompatible_prefix_or_edited_plan_rejected_before_any_new_write(library,tmp_path,change):
    with importer.forecast.open_lab(library,tmp_path) as lab:
        run(lab,importer.make_plan(plan()['records'][:4]));before=history(lab)
        value=plan()
        if change=='value':
            data=copy.deepcopy(value['records']);data[0]['value']=999;value=importer.make_plan(data)
        elif change=='identity':
            data=copy.deepcopy(value['records']);data[0]['observation_id']='renamed';value=importer.make_plan(data)
        elif change=='shorter': value=importer.make_plan(value['records'][:3])
        else: value['commands'][0]['command']['value']=999
        with pytest.raises(ValueError): run(lab,value)
        assert history(lab)==before


def test_existing_measurements_cannot_receive_backdated_predictions(library,tmp_path):
    with importer.forecast.open_lab(library,tmp_path) as lab:
        for row in plan()['records'][:4]: lab.execute(dict(op='observe',scope='csv',**row))
        before=history(lab)
        with pytest.raises(ValueError,match='historical backfill refused'): run(lab)
        assert history(lab)==before


def test_missing_prediction_at_current_prefix_can_be_created_after_interruption(library,tmp_path):
    with importer.forecast.open_lab(library,tmp_path) as lab:
        for row in plan()['records'][:3]: lab.execute(dict(op='observe',scope='csv',**row))
    with importer.forecast.open_lab(library,tmp_path) as lab:
        result,_=run(lab)
        assert result['status']['observation_count']==8 and result['status']['prediction_count']==5


def test_unrelated_prediction_in_scope_is_not_silently_adopted(library,tmp_path):
    with importer.forecast.open_lab(library,tmp_path) as lab:
        for row in plan()['records'][:3]: lab.execute(dict(op='observe',scope='csv',**row))
        lab.execute(dict(op='predict',scope='csv',prediction_id='manual',entity='ab',target_tick=3))
        before=history(lab)
        with pytest.raises(ValueError,match='outside this CSV plan'): run(lab)
        assert history(lab)==before


def test_partial_prediction_repaired_before_prefix_replay(library,tmp_path,monkeypatch):
    original=importer.forecast.selection.recent.freeze
    def fail(*args,**kwargs): raise RuntimeError('injected interrupted prediction')
    with importer.forecast.open_lab(library,tmp_path) as lab:
        monkeypatch.setattr(importer.forecast.selection.recent,'freeze',fail)
        with pytest.raises(RuntimeError,match='partially persisted'): run(lab)
        assert lab.execute(dict(op='status',scope='csv'))['result']['repair_prediction_ids']
        monkeypatch.setattr(importer.forecast.selection.recent,'freeze',original)
    with importer.forecast.open_lab(library,tmp_path) as lab:
        result,events=run(lab)
        assert result['recovery_commands']==1 and events[0]['phase']=='recovery'
        assert events[0]['response']['result']['status']=='COMPLETED_RETRY'
        assert result['status']['repair_prediction_ids']==[]
        assert len(history(lab)['journal'])==30


def test_partial_observation_linkage_repaired_before_prefix_replay(library,tmp_path,monkeypatch):
    original=importer.forecast.selection.recent.link_measurement
    def fail(*args,**kwargs): raise RuntimeError('injected interrupted linkage')
    with importer.forecast.open_lab(library,tmp_path) as lab:
        monkeypatch.setattr(importer.forecast.selection.recent,'link_measurement',fail)
        with pytest.raises(RuntimeError,match='partially persisted'): run(lab)
        assert lab.execute(dict(op='status',scope='csv'))['result']['repair_observation_ids']==['m3']
        monkeypatch.setattr(importer.forecast.selection.recent,'link_measurement',original)
    with importer.forecast.open_lab(library,tmp_path) as lab:
        result,events=run(lab)
        assert result['recovery_commands']==1 and events[0]['phase']=='recovery'
        assert events[0]['response']['result']['status']=='EXACT_REPLAY'
        assert result['status']['repair_observation_ids']==[]
        assert len(history(lab)['entries'])==8 and len(history(lab)['journal'])==30


def test_later_csv_values_do_not_leak_into_first_frozen_prediction(library,tmp_path):
    models=[]
    for index,content in enumerate((DATA,DATA.replace('m3,ab,3,17','m3,ab,3,99'))):
        with importer.forecast.open_lab(library,tmp_path/str(index)) as lab:
            run(lab,plan(content))
            target=importer.forecast.ids(importer.automatic_id('csv','ab',3))['selector']
            entries=[e for e in history(lab)['journal'] if e['event']['op']=='FORECAST' and e['event']['forecast_id']==target]
            models.append(entries[0])
    assert models[0]==models[1]


def test_import_does_not_call_simulator(library,tmp_path,monkeypatch):
    def forbidden(*args): raise AssertionError('CSV values must not be replaced by simulator values')
    monkeypatch.setattr(importer.forecast.base,'measure',forbidden)
    with importer.forecast.open_lab(library,tmp_path) as lab:
        result,_=run(lab,importer.make_plan(plan()['records'][:3]))
        assert result['status']['observation_count']==3


def test_cli_dry_run_and_bad_last_row_do_not_open_database(library,tmp_path):
    root=Path(__file__).resolve().parents[1];script=root/'scripts/trajectory_forecast_csv.py'
    backend=tmp_path/'never-created'
    dry=subprocess.run([sys.executable,str(script),'--dry-run','--library','/missing-library','--data-dir',str(backend)],
                       input=DATA,cwd=root,capture_output=True,text=True,check=True)
    assert json.loads(dry.stdout)['phase']=='plan' and not backend.exists()
    bad=subprocess.run([sys.executable,str(script),'--library',str(library),'--data-dir',str(backend)],
                       input=DATA.replace('m7,ab,7,21','m7,ab,7,invalid'),cwd=root,capture_output=True,text=True)
    assert bad.returncode==2 and json.loads(bad.stdout)['data_operations_started'] is False
    assert not backend.exists()


def test_actual_csv_cli_runs_and_replays_in_another_process(library,tmp_path):
    root=Path(__file__).resolve().parents[1]
    command=[sys.executable,str(root/'scripts/trajectory_forecast_csv.py'),'--input',str(root/'examples/forecast-lab-measurements.csv'),
             '--library',str(library),'--data-dir',str(tmp_path)]
    first=subprocess.run(command,cwd=root,capture_output=True,text=True,check=True)
    initial=[json.loads(line) for line in first.stdout.splitlines()]
    assert len(initial)==14 and initial[-1]['phase']=='summary'
    assert initial[-1]['status']['observation_count']==8 and initial[-1]['status']['prediction_count']==5
    second=subprocess.run(command,cwd=root,capture_output=True,text=True,check=True)
    replay=[json.loads(line) for line in second.stdout.splitlines()]
    assert initial[-1]==replay[-1]
    assert all(e['response']['result']['status']=='EXACT_REPLAY' for e in replay[:-1])
