import copy
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import trajectory_forecast_report as report
import trajectory_forecast_csv as importer

DATA='observation_id,entity,tick,value\nm0,ab,0,10\nm1,ab,1,11\nm2,ab,2,12\nm3,ab,3,17\nm4,ab,4,18\nm5,ab,5,19\nm6,ab,6,20\nm7,ab,7,21\n'


class Page(HTMLParser):
    def __init__(self,text):
        super().__init__()
        self.tags=[];self.attrs=[]
        self.feed(text)

    def handle_starttag(self,tag,attrs):
        self.tags.append(tag);self.attrs.append((tag,dict(attrs)))


class ReadOnlyLab:
    def __init__(self):
        self.lock=threading.RLock();self.calls=[]
        self.history=dict(entries=[],journal=[],predictions=[])
        self.status=dict(limits=report.forecast.LIMITS,repair_prediction_ids=[],repair_observation_ids=[])

    def execute(self,request):
        self.calls.append(request)
        assert request['op'] in ('history','status')
        return dict(result=copy.deepcopy(getattr(self,request['op'])))


def empty():
    return report.collect_report(ReadOnlyLab())


def test_snapshot_collects_only_reads_and_is_stable_without_timestamps():
    lab=ReadOnlyLab()
    first=report.collect_report(lab,'csv');second=report.collect_report(lab,'csv')
    assert first==second
    assert [x['op'] for x in lab.calls]==['history','status','history','status']
    assert all(x['scope']=='csv' for x in lab.calls)
    assert first['qualified'] is False and first['answer'] is None
    assert first['factual_quality_status']=='NOT_EVALUATED'


def test_empty_html_has_no_invented_points_and_render_is_pure():
    value=empty();before=copy.deepcopy(value)
    html=report.render_html(value)
    assert 'Sem dados neste escopo.' in html and '<svg' not in html
    assert value==before


def test_html_escapes_title_and_payload_without_active_content():
    value=empty();value['scope']='</pre><script>alert(1)</script>'
    value['snapshot_id']=report.forecast.base.fingerprint({k:v for k,v in value.items() if k!='snapshot_id'})
    html=report.render_html(value,title='</title><script>alert(2)</script>')
    page=Page(html)
    assert not set(page.tags)&{'script','iframe','img','link','object','embed','form'}
    assert all(not key.lower().startswith('on') for _,attrs in page.attrs for key in attrs)
    assert '&lt;script&gt;' in html
    assert any(tag=='meta' and attrs.get('http-equiv')=='Content-Security-Policy' for tag,attrs in page.attrs)
    assert any(tag=='meta' and attrs.get('name')=='viewport' for tag,attrs in page.attrs)
    assert '@media(max-width:600px)' in html and 'table-wrap' in html


@pytest.mark.parametrize('point',[
    dict(entity='ab',tick=True,value=1),
    dict(entity='ab',tick=0,value=float('nan')),
    dict(entity='ab',tick=1001,value=1),
    dict(entity='ab',tick=0,value=10001),
    dict(entity='<script>',tick=0,value=1),
])
def test_plot_rejects_invalid_numeric_or_entity_fields(point):
    with pytest.raises(ValueError): report.numeric_point(point)


def test_outputs_are_distinct_and_outside_source_directory(tmp_path):
    data=tmp_path/'db'
    with pytest.raises(ValueError,match='outside'): report.output_targets(data,data/'export.html')
    with pytest.raises(ValueError,match='distinct'): report.output_targets(data,tmp_path/'a.html',tmp_path/'a.html')
    with pytest.raises(ValueError,match='extension'): report.output_targets(data,tmp_path/'a.txt')


def test_all_output_paths_are_preflighted_before_html_creation(tmp_path):
    html=tmp_path/'new.html';json_path=tmp_path/'existing.json';json_path.write_text('keep')
    with pytest.raises(FileExistsError): report.write_report(empty(),tmp_path/'db',html,json_path)
    assert not html.exists() and json_path.read_text()=='keep'


@pytest.mark.parametrize('broken',[False,True])
def test_existing_or_broken_symlinks_are_refused(tmp_path,broken):
    target=tmp_path/'target.html'
    if not broken: target.write_text('keep')
    link=tmp_path/'link.html';link.symlink_to(target)
    with pytest.raises(FileExistsError): report.write_report(empty(),tmp_path/'db',link)
    assert link.is_symlink()
    if not broken: assert target.read_text()=='keep'


def test_changed_snapshot_is_refused_before_creating_output(tmp_path):
    value=empty();value['counts']['matches']=999
    target=tmp_path/'new'/'page.html'
    with pytest.raises(ValueError,match='snapshot'): report.write_report(value,tmp_path/'db',target)
    assert not target.parent.exists()


def test_export_matches_json_and_refuses_overwrite(tmp_path):
    value=empty();html=tmp_path/'out'/'page.html';json_path=tmp_path/'out'/'page.json'
    paths=report.write_report(value,tmp_path/'db',html,json_path)
    assert json.loads(json_path.read_text())==value
    assert paths==dict(html=str(html),json=str(json_path))
    assert value['snapshot_id'] in html.read_text()
    with pytest.raises(FileExistsError): report.write_report(value,tmp_path/'db',html)


@pytest.fixture
def library():
    path=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so')).resolve()
    if not path.exists():
        if 'MEMORIA_NATIVE_LIBRARY' in os.environ: pytest.fail('Explicit native BDR library is missing')
        pytest.skip('Native integration runs in pinned-BDR CI')
    return path


def history(lab):
    return lab.execute(dict(op='history',scope='csv'))['result']


def seed(lab,full=True):
    plan=importer.make_plan(importer.read_csv(io.StringIO(DATA)),'csv')
    if full: importer.import_plan(lab,plan,io.StringIO())
    else:
        for row in plan['records'][:3]: lab.execute(dict(op='observe',scope='csv',**row))


def predict(lab):
    lab.execute(dict(op='predict',scope='csv',prediction_id='p3',entity='ab',target_tick=3))


def observe(lab,value,obs='m3'):
    lab.execute(dict(op='observe',scope='csv',observation_id=obs,entity='ab',tick=3,value=value))


def test_native_snapshot_preserves_errors_abstentions_and_cold_parity(library,tmp_path,monkeypatch):
    with report.forecast.open_lab(library,tmp_path) as lab:
        seed(lab);before=history(lab)
        def forbidden(*args,**kwargs): raise AssertionError('report must never use a simulator')
        monkeypatch.setattr(report.forecast.base,'measure',forbidden)
        value=report.collect_report(lab,'csv')
        assert history(lab)==before
        assert value['counts']==dict(observations=8,predictions=5,matches=1,mismatches=1,abstentions=3,pending=0,conflicts=0,unverifiable=0,incomplete=0)
        by_tick={p['target_tick']:p for p in value['predictions']}
        assert by_tick[3]['proposal']['value']==13
        assert by_tick[3]['linked_observations'][0]['value']==17
        assert by_tick[3]['observed_minus_proposed']==4
        assert by_tick[7]['selected_rule']=='recent_suffix' and by_tick[7]['observed_minus_proposed']==0
        assert all(by_tick[t]['observed_minus_proposed'] is None for t in (4,5,6))
    with report.forecast.open_lab(library,tmp_path) as lab:
        assert report.collect_report(lab,'csv')==value
        assert history(lab)==before


def test_native_chart_uses_only_selected_proposals_and_retains_all_measurements(library,tmp_path):
    with report.forecast.open_lab(library,tmp_path) as lab:
        seed(lab);value=report.collect_report(lab,'csv')
    page=Page(report.render_html(value))
    measured=[a for _,a in page.attrs if a.get('data-series')=='observed']
    proposed=[a for _,a in page.attrs if a.get('data-series')=='proposal']
    assert len(measured)==8 and len(proposed)==2
    assert {(a['data-tick'],a['data-value']) for a in proposed}=={('3','13'),('7','21')}
    assert {(a['data-tick'],a['data-value']) for a in measured}=={(str(t),str(v)) for t,v in enumerate((10,11,12,17,18,19,20,21))}


def test_incomplete_forecast_is_reported_without_automatic_repair(library,tmp_path,monkeypatch):
    with report.forecast.open_lab(library,tmp_path) as lab:
        seed(lab,False)
        def fail(*args,**kwargs): raise RuntimeError('injected freeze interruption')
        monkeypatch.setattr(report.forecast.selection.recent,'freeze',fail)
        with pytest.raises(RuntimeError,match='partially persisted'): predict(lab)
        before=history(lab);value=report.collect_report(lab,'csv')
        assert value['counts']['incomplete']==1 and value['repair_prediction_ids']==['p3']
        assert value['predictions'][0]['linked_observations']==[]
        assert 'Retomada necessária' in report.render_html(value)
        assert history(lab)==before


def test_unlinked_raw_measurement_is_never_inferred_as_a_selector_outcome(library,tmp_path,monkeypatch):
    with report.forecast.open_lab(library,tmp_path) as lab:
        seed(lab,False);predict(lab)
        def fail(*args,**kwargs): raise RuntimeError('injected linkage interruption')
        monkeypatch.setattr(report.forecast.selection.recent,'link_measurement',fail)
        with pytest.raises(RuntimeError,match='partially persisted'): observe(lab,17)
        before=history(lab);value=report.collect_report(lab,'csv');p=value['predictions'][0]
        assert value['counts']['observations']==4 and value['repair_observation_ids']==['m3']
        assert p['report_status']=='PENDING' and p['linked_observations']==[]
        assert p['observed_minus_proposed'] is None and history(lab)==before


def test_conflicting_values_remain_visible_without_averaging(library,tmp_path):
    with report.forecast.open_lab(library,tmp_path) as lab:
        seed(lab,False);predict(lab);observe(lab,13);observe(lab,99,'conflict')
        before=history(lab);value=report.collect_report(lab,'csv');p=value['predictions'][0]
        assert value['counts']['conflicts']==1 and p['observed_minus_proposed'] is None
        assert sorted(v['value'] for v in p['linked_observations'])==[13,99]
        assert 'Medições conflitantes' in report.render_html(value)
        assert history(lab)==before


def test_unverifiable_prefix_is_flagged_and_excluded_from_chart(library,tmp_path):
    with report.forecast.open_lab(library,tmp_path) as lab:
        seed(lab,False);predict(lab)
        report.forecast.base.persist(lab.native,[dict(hierarchy_id='forecast-lab:csv',source_id='fl:observation:injected',
            sequence=0,text='M[ab;0]=99.',source_kind='user_turn')])
        before=history(lab);value=report.collect_report(lab,'csv')
        assert value['counts']['unverifiable']==1
        assert value['predictions'][0]['proposal']['value']==13
        assert value['predictions'][0]['observed_minus_proposed'] is None
        html=report.render_html(value)
        assert 'Histórico não verificável' in html and 'data-series="proposal"' not in html
        assert history(lab)==before


def cli(library,data,html,json_path=None):
    root=Path(__file__).resolve().parents[1]
    command=[sys.executable,str(root/'scripts/trajectory_forecast_report.py'),'--library',str(library),
             '--data-dir',str(data),'--scope','csv','--html',str(html)]
    if json_path is not None: command.extend(['--json',str(json_path)])
    return subprocess.run(command,cwd=root,capture_output=True,text=True)


def test_real_cli_exports_reopens_and_preserves_logical_state(library,tmp_path):
    data=tmp_path/'db'
    with report.forecast.open_lab(library,data) as lab:
        seed(lab);before=history(lab);expected=report.collect_report(lab,'csv')
    first=cli(library,data,tmp_path/'first.html',tmp_path/'first.json')
    assert first.returncode==0,first.stderr
    response=json.loads(first.stdout)
    assert response['ok'] is True and response['native_mutations_requested'] is False
    assert response['qualified'] is False and response['counts']['mismatches']==1
    assert json.loads((tmp_path/'first.json').read_text())==expected
    second=cli(library,data,tmp_path/'second.html',tmp_path/'second.json')
    assert second.returncode==0,second.stderr
    assert (tmp_path/'first.json').read_bytes()==(tmp_path/'second.json').read_bytes()
    saved=(tmp_path/'first.html').read_bytes()
    assert cli(library,data,tmp_path/'first.html').returncode==2
    assert (tmp_path/'first.html').read_bytes()==saved
    with report.forecast.open_lab(library,data) as lab: assert history(lab)==before


@pytest.mark.parametrize('existing_empty',[False,True])
def test_cli_refuses_missing_or_empty_source_without_initializing_it(tmp_path,existing_empty):
    data=tmp_path/'db'
    if existing_empty: (data/'native').mkdir(parents=True)
    result=cli('/missing-library',data,tmp_path/'page.html')
    assert result.returncode==2 and json.loads(result.stdout)['ok'] is False
    assert not (tmp_path/'page.html').exists()
    if existing_empty: assert list((data/'native').iterdir())==[]
    else: assert not data.exists()
