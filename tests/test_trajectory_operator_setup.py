import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_operator_setup import BDR_COMMIT,MARKER,REPORT,ROOT,dependency,owned_work_dir,prepare,smoke,validate_data_separation


def test_check_with_missing_tools_is_read_only_and_does_not_open_pilot(tmp_path):
    script=ROOT/'scripts/trajectory_operator_setup.py'
    work=tmp_path/'build';pilot=tmp_path/'pilot'
    run=subprocess.run([sys.executable,str(script),'--check','--work-dir',str(work),'--data-dir',str(pilot)],
                       text=True,capture_output=True,env=dict(os.environ,PATH=''))
    assert run.returncode==2
    result=json.loads(run.stdout)
    assert result['status']=='BLOCKED' and not result['checks']['cmake']
    assert not work.exists() and not pilot.exists()


def test_existing_data_folder_is_never_claimed_or_rewritten(tmp_path):
    folder=tmp_path/'operator-data';folder.mkdir();content=folder/'important-data'
    content.write_bytes(b'preserve this exact state')
    with pytest.raises(ValueError,match='Pasta existente'):owned_work_dir(folder)
    assert content.read_bytes()==b'preserve this exact state'
    assert sorted(p.name for p in folder.iterdir())==['important-data']


def test_owned_build_directory_is_reusable_but_wrong_configuration_is_rejected(tmp_path):
    folder=owned_work_dir(tmp_path/'build')
    assert owned_work_dir(folder)==folder
    marker=json.loads((folder/MARKER).read_text());marker['bdr_commit']='different'
    (folder/MARKER).write_text(json.dumps(marker))
    with pytest.raises(ValueError,match='outra configuração'):owned_work_dir(folder)


@pytest.mark.parametrize('relation',['same','nested_data','nested_build'])
def test_data_and_build_paths_cannot_overlap(tmp_path,relation):
    work=tmp_path/'build'
    data=work if relation=='same' else work/'data' if relation=='nested_data' else tmp_path
    with pytest.raises(ValueError,match='sem sobreposição'):validate_data_separation(work,data)
    assert not work.exists()


def test_wrong_bdr_revision_is_rejected_without_checkout_or_reset(tmp_path):
    git=__import__('shutil').which('git')
    if not git:pytest.skip('git required')
    source=tmp_path/'source'
    subprocess.run([git,'init',str(source)],check=True,capture_output=True)
    subprocess.run([git,'-C',str(source),'-c','user.name=Setup Test','-c','user.email=test@example.invalid',
                    'commit','--allow-empty','-m','local fixture'],check=True,capture_output=True)
    before=subprocess.check_output([git,'-C',str(source),'rev-parse','HEAD'],text=True).strip()
    with pytest.raises(ValueError,match='commit fixado'):
        dependency({'git':{'path':git}},tmp_path,source)
    assert subprocess.check_output([git,'-C',str(source),'rev-parse','HEAD'],text=True).strip()==before
    assert before!=BDR_COMMIT


def test_missing_tools_reject_prepare_before_creating_build(tmp_path):
    with pytest.raises(ValueError):prepare(tmp_path/'build',{'status':'BLOCKED'})
    assert not (tmp_path/'build').exists()


def test_native_smoke_is_temporary_and_does_not_touch_existing_pilot_data(tmp_path):
    library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so')).resolve()
    if not library.exists():pytest.skip('native library required')
    pilot=tmp_path/'existing-pilot';pilot.mkdir();marker=pilot/'keep'
    marker.write_text('existing state')
    work=owned_work_dir(tmp_path/'build')
    result=smoke(library,work)
    assert result['status']=='PASS' and all(result['checks'].values())
    assert result['temporary_storage_removed'] and marker.read_text()=='existing state'
    assert sorted(p.name for p in work.iterdir())==[MARKER]


def test_run_requires_explicit_identity_and_data_folder_before_any_build(tmp_path):
    script=ROOT/'scripts/trajectory_operator_setup.py';work=tmp_path/'build'
    run=subprocess.run([sys.executable,str(script),'--run','--work-dir',str(work)],capture_output=True,text=True)
    assert run.returncode==2 and not work.exists()


@pytest.mark.parametrize('actor',[' ','x'*129])
def test_invalid_run_identity_is_rejected_before_preparing(tmp_path,actor):
    work=tmp_path/'build'
    run=subprocess.run([sys.executable,str(ROOT/'scripts/trajectory_operator_setup.py'),'--run','--work-dir',str(work),
                        '--data-dir',str(tmp_path/'data'),'--actor',actor],capture_output=True,text=True)
    assert run.returncode==2 and not work.exists() and not (tmp_path/'data').exists()


def test_configuration_failure_replaces_stale_readiness_without_touching_pilot(tmp_path):
    import shutil
    git=shutil.which('git');failed_tool=shutil.which('false');bdr=ROOT/'deps/resolutive-DB'
    if not git or not failed_tool or not bdr.exists():pytest.skip('local pinned dependency and Unix tools required')
    work=owned_work_dir(tmp_path/'build');(work/REPORT).write_text('{"status":"READY_FOR_LOCAL_PILOT"}')
    pilot=tmp_path/'pilot';pilot.mkdir();(pilot/'keep').write_text('existing data')
    checks=dict(status='TOOLS_AVAILABLE',tools={'git':{'path':git},'cmake':{'path':failed_tool},'cc':{'path':'cc'},'c++':{'path':'c++'}})
    with pytest.raises(RuntimeError,match='Comando falhou'):prepare(work,checks,bdr)
    report=json.loads((work/REPORT).read_text())
    assert report['status']=='FAILED' and not report['pilot_data_opened_during_prepare']
    assert (pilot/'keep').read_text()=='existing data'
