#!/usr/bin/env python3
"""Prepare an isolated Linux operator pilot build; do not install system packages."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT=Path(__file__).resolve().parents[1]
BDR_COMMIT='317882a00f041fc1568ff986af8016b09453f21a'
BDR_URL='https://github.com/marceloroldao/resolutive-DB.git'
MARKER='operator-build-owner.json'
REPORT='operator-pilot-ready.json'


def command(argv,timeout=None):
    result=subprocess.run([str(x) for x in argv],text=True,capture_output=True,
                          env=dict(os.environ,GIT_TERMINAL_PROMPT='0'),timeout=timeout)
    if result.returncode:
        raise RuntimeError('Comando falhou: '+str(argv[0])+'\n'+(result.stderr or result.stdout)[-4000:])
    return result.stdout.strip()


def preflight(cmake=None):
    checks=dict(linux=sys.platform.startswith('linux'),python=sys.version_info>=(3,10))
    tools={}
    for name,override in (('git',None),('cmake',cmake),('cc',None),('c++',None),('make',None)):
        path=str(Path(override).resolve()) if override else shutil.which(name)
        try:
            if not path or not Path(path).is_file() or not os.access(path,os.X_OK):raise ValueError('not executable')
            versions=command([path,'--version'],timeout=15).splitlines()
            if not versions:raise ValueError('tool returned no version')
            version=versions[0]
            if name=='cmake':
                match=re.search(r'version (\d+)\.(\d+)',version)
                if not match or tuple(map(int,match.groups()))<(3,22):raise ValueError('CMake >= 3.22 required')
            tools[name]=dict(path=path,version=version);checks[name]=True
        except (ValueError,RuntimeError,OSError,subprocess.TimeoutExpired) as error:
            checks[name]=False;tools[name]=dict(path=path,error=str(error))
    return dict(format='memoria.ia-operator-preflight-v1',status='TOOLS_AVAILABLE' if all(checks.values()) else 'BLOCKED',
                checks=checks,tools=tools,compilation_checked=False,system_packages_installed=False)


def owned_work_dir(path):
    path=Path(path).resolve();marker=path/MARKER
    expected=dict(format='memoria.ia-operator-build-dir-v1',repository=str(ROOT),bdr_commit=BDR_COMMIT)
    if path.exists():
        if not path.is_dir():raise ValueError('O diretório de build precisa ser uma pasta.')
        if any(path.iterdir()):
            try:owner=json.loads(marker.read_text())
            except (OSError,ValueError) as error:raise ValueError('Pasta existente não pertence ao preparador; escolha uma pasta nova ou vazia.') from error
            if owner!=expected:raise ValueError('Pasta de build pertence a outra configuração; escolha uma pasta nova.')
    path.mkdir(parents=True,exist_ok=True)
    marker.write_text(json.dumps(expected,ensure_ascii=False,indent=2)+'\n')
    return path


def validate_data_separation(work_dir,data_dir):
    work=Path(work_dir).resolve();data=Path(data_dir).resolve()
    if work==data or work in data.parents or data in work.parents:
        raise ValueError('Use pastas separadas, sem sobreposição, para build e dados do piloto.')


def dependency(tools,work,bdr_root=None):
    path=Path(bdr_root).resolve() if bdr_root else work/'resolutive-DB'
    git=tools['git']['path']
    if not path.exists():
        if bdr_root:raise ValueError('O checkout BDR informado não existe.')
        command([git,'clone','--no-checkout',BDR_URL,path])
        command([git,'-C',path,'checkout','--detach',BDR_COMMIT])
    top=Path(command([git,'-C',path,'rev-parse','--show-toplevel'])).resolve()
    if top!=path:raise ValueError('Informe a raiz exata de um checkout BDR.')
    if command([git,'-C',path,'rev-parse','HEAD'])!=BDR_COMMIT:
        raise ValueError('Checkout BDR não está no commit fixado; escolha outro checkout ou uma pasta nova de build.')
    if command([git,'-C',path,'status','--porcelain']):
        raise ValueError('Checkout BDR contém alterações; elas não serão descartadas pelo preparador.')
    return path


def smoke(library,work):
    # Imports are lazy: --check can explain missing tools without loading the native runtime.
    sys.path.insert(0,str(ROOT/'src'))
    from trajectory_feedback_session import FeedbackSession
    checks={}
    with tempfile.TemporaryDirectory(prefix='operator-smoke-',dir=work) as directory:
        directory=Path(directory)
        with FeedbackSession(library,directory) as session:
            session.execute(dict(op='observe',event_id='setup-observation',text='Observação do teste de inicialização.'))
            session.execute(dict(op='observe',event_id='setup-generated',text='Conteúdo gerado do teste.',source_kind='assistant_generated'))
            request=dict(text='Pergunta de verificação?',offers=[dict(offer_id='setup-example',provenance='teste programado',
                         examples=[dict(source_text='Origem do exemplo.',target_text='Conteúdo associado.')])])
            learning=session.execute(dict(op='history'))
            reviewed=session.execute(dict(op='review_examples',**request))
            opened=session.execute(dict(op='open_review',**request))['result']['event']
            decision=dict(op='record_review_decision',receipt_id=opened['receipt_id'],decision_id='setup-decision',actor_id='setup-check',
                          choice='defer',offer_id=None,reason='Teste programado de persistência; não é avaliação humana.')
            session.execute(decision)
            outcome=dict(op='record_review_outcome',decision_id='setup-decision',after_receipt_id=opened['receipt_id'],
                         outcome_id='setup-outcome',actor_id='setup-check',judgement='uncertain',reason='Verificação técnica de inicialização.')
            session.execute(outcome)
            audit=session.execute(dict(op='review_outcomes'))
            checks.update(read_only_review=session.execute(dict(op='review_examples',**request))==reviewed,
                          no_example_incorporation=session.execute(dict(op='history'))==learning,
                          generated_origin_preserved=learning['result']['entries'][1]['source_kind']=='assistant_generated',
                          receipt_decision_outcome_present=len(audit['result']['receipts'])==len(audit['result']['decisions'])==len(audit['result']['outcomes'])==1)
        with FeedbackSession(library,directory) as cold:
            checks.update(cold_history=cold.execute(dict(op='history'))==learning,
                          cold_review=cold.execute(dict(op='review_examples',**request))==reviewed,
                          cold_audit=cold.execute(dict(op='review_outcomes'))==audit,
                          decision_replay=cold.execute(decision)['result']['status']=='EXACT_REPLAY',
                          outcome_replay=cold.execute(outcome)['result']['status']=='EXACT_REPLAY')
    if not all(checks.values()):raise RuntimeError('A verificação temporária de persistência falhou.')
    return dict(status='PASS',checks=checks,temporary_storage_removed=True,human_evaluation_status='NOT_PERFORMED')


def prepare(work_dir,checks,bdr_root=None,jobs=2):
    if checks['status']!='TOOLS_AVAILABLE':raise ValueError('Ferramentas ausentes ou incompatíveis; confira --check.')
    if not 1<=jobs<=8:raise ValueError('Use de uma a oito tarefas de compilação.')
    work=owned_work_dir(work_dir);report_path=work/REPORT
    report=dict(format='memoria.ia-operator-pilot-build-v1',status='PREPARING',work_dir=str(work),preflight=checks,
                bdr_commit=BDR_COMMIT,pilot_data_opened_during_prepare=False,system_packages_installed=False)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    try:
        tools=checks['tools'];git=tools['git']['path'];cmake=tools['cmake']['path']
        report['source_commit']=command([git,'-C',ROOT,'rev-parse','HEAD'])
        report['runtime_entry_sha256']={name:hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest()
                                        for name in ('trajectory_operator_setup.py','trajectory_review_wizard.py','trajectory_pilot_export.py')}
        if command([git,'-C',ROOT,'status','--porcelain','--','native/mobile','include']):
            raise ValueError('Há alterações nativas não registradas; use uma revisão nativa consolidada para o piloto.')
        print('Conferindo a dependência BDR fixada...',flush=True)
        bdr=dependency(tools,work,bdr_root)
        build=work/'native-build'
        command([cmake,'-S',ROOT/'native/mobile','-B',build,'-G','Unix Makefiles','-DCMAKE_BUILD_TYPE=Release',
                 '-DMEMORIA_BDR_ROOT='+str(bdr),'-DCMAKE_C_COMPILER='+tools['cc']['path'],'-DCMAKE_CXX_COMPILER='+tools['c++']['path']])
        print('Compilando a biblioteca local...',flush=True)
        command([cmake,'--build',build,'--target','memoria_mobile','--parallel',str(jobs)])
        library=build/'libmemoria_mobile.so'
        if not library.is_file():raise RuntimeError('A biblioteca nativa esperada não foi produzida.')
        report.update(library=str(library),library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),bdr_root=str(bdr))
        print('Verificando persistência em memória temporária...',flush=True)
        report['smoke']=smoke(library,work)
        report['status']='READY_FOR_LOCAL_PILOT'
    except Exception as error:
        report.update(status='FAILED',error=str(error));raise
    finally:
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',type=Path,default=ROOT/'build/operator-pilot')
    parser.add_argument('--cmake')
    parser.add_argument('--bdr-root',type=Path)
    parser.add_argument('--jobs',type=int,default=2)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--scope',default='principal')
    parser.add_argument('--actor')
    args=parser.parse_args()
    if args.check and args.run:parser.error('--check e --run são alternativas.')
    if args.run and (not args.data_dir or not args.actor):parser.error('--run exige --data-dir e --actor explícitos.')
    if args.run:
        if not args.actor.strip() or len(args.actor)>128:parser.error('--actor exige de 1 a 128 caracteres não vazios.')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',args.scope):parser.error('--scope inválido.')
        try:validate_data_separation(args.work_dir,args.data_dir)
        except ValueError as error:parser.error(str(error))
    checks=preflight(args.cmake)
    if args.check or checks['status']=='BLOCKED':
        print(json.dumps(checks,ensure_ascii=False,indent=2));raise SystemExit(0 if checks['status']=='TOOLS_AVAILABLE' else 2)
    try:
        report=prepare(args.work_dir,checks,args.bdr_root,args.jobs)
    except (ValueError,RuntimeError,OSError) as error:parser.exit(1,'Preparação recusada ou incompleta: '+str(error)+'\n')
    print('Preparação concluída; teste temporário de persistência aprovado.',flush=True)
    print('Relatório: '+str(Path(report['work_dir'])/REPORT),flush=True)
    if args.run:
        environment=dict(os.environ)
        environment['PYTHONPATH']=str(ROOT/'src')+(os.pathsep+environment['PYTHONPATH'] if environment.get('PYTHONPATH') else '')
        result=subprocess.run([sys.executable,str(ROOT/'scripts/trajectory_review_wizard.py'),'--library',report['library'],
                               '--data-dir',str(args.data_dir),'--scope',args.scope,'--actor',args.actor],env=environment)
        raise SystemExit(result.returncode)


if __name__=='__main__':main()
