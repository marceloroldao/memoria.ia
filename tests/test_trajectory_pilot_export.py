import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_trajectory_review_wizard import session, run_script, review_inputs
from trajectory_demonstration_review_probe import fixture_and_offers, populate
from trajectory_feedback_session import FeedbackSession
from trajectory_pilot_export import export, snapshot
from trajectory_region_evidence_probe import fingerprint


@pytest.mark.parametrize('choice,judgement', [('p','worsened'),('d','uncertain')])
def test_export_keeps_negative_and_uncertain_results_across_restart(session, tmp_path, choice, judgement):
    active, library, directory = session
    fixture, offers = fixture_and_offers('pressure','unseen_identity')
    populate(active, fixture)
    scope = fixture['scope']
    run_script(active,scope,review_inputs(fixture,[offers[1]],'d')+[choice,'Resultado programado, sem operador humano.','0'])
    active.execute(dict(op='observe', scope='other', text='Conteúdo de outro escopo.',event_id='other'))
    before = snapshot(active,scope)
    path = tmp_path.parent / (tmp_path.name+'-evidence.json')
    assert export(active,scope,path) == before == snapshot(active,scope)
    assert path.stat().st_mode & 0o777 == 0o600
    assert 'Conteúdo de outro escopo.' not in path.read_text()
    assert before['review_audit']['result']['outcomes'][0]['event']['judgement'] == judgement
    assert before['decisions_without_outcomes'] == []
    assert before['human_evaluation_status'] == 'NOT_VERIFIED'
    saved = json.loads(path.read_text()); digest = saved.pop('sha256')
    assert fingerprint(saved) == digest
    active.close()
    with FeedbackSession(library,directory) as cold:
        assert snapshot(cold,scope) == before


def test_export_preserves_unfinished_decisions_and_menu_does_not_record_events(session,tmp_path):
    active, _, _ = session
    fixture, offers = fixture_and_offers('pressure','unseen_identity'); populate(active,fixture)
    run_script(active,fixture['scope'],review_inputs(fixture,[offers[1]],'d')+['s','0'])
    before = snapshot(active,fixture['scope'])
    path = tmp_path.parent / (tmp_path.name+'-menu.json')
    output = run_script(active,fixture['scope'],['6',str(path),'0'])
    assert any('Evidência exportada' in line for line in output)
    assert len(before['decisions_without_outcomes']) == 1
    assert json.loads(path.read_text()) == before == snapshot(active,fixture['scope'])


def test_export_refuses_existing_file_symlink_and_data_directory(session,tmp_path):
    active, _, directory = session
    target = tmp_path.parent / (tmp_path.name+'-existing.json'); target.write_text('preserve')
    with pytest.raises(FileExistsError): export(active,'principal',target)
    assert target.read_text() == 'preserve'
    link = target.with_suffix('.link'); link.symlink_to(target)
    with pytest.raises(FileExistsError): export(active,'principal',link)
    assert target.read_text() == 'preserve'
    alias = target.with_suffix('.dir'); alias.symlink_to(directory, target_is_directory=True)
    with pytest.raises(ValueError): export(active,'principal',alias/'unsafe.json')
    assert not (directory/'unsafe.json').exists()
    assert not list(target.parent.glob('.pilot-export-*'))


def test_export_publication_failure_leaves_no_partial_file_or_new_event(session,tmp_path,monkeypatch):
    active, _, _ = session
    before = snapshot(active,'principal'); path = tmp_path.parent / (tmp_path.name+'-failed.json')
    def fail(*args): raise OSError('simulated publication failure')
    monkeypatch.setattr(os,'link',fail)
    with pytest.raises(OSError): export(active,'principal',path)
    assert not path.exists() and not list(path.parent.glob('.pilot-export-*'))
    assert snapshot(active,'principal') == before


def test_real_terminal_exports_empty_scope_without_new_observations(session,tmp_path):
    _, library, _ = session
    path = tmp_path/'terminal.json'
    script = Path(__file__).resolve().parents[1]/'scripts'/'trajectory_review_wizard.py'
    run = subprocess.run([sys.executable,str(script),'--library',str(library.resolve()),
                          '--data-dir',str(tmp_path/'pilot'),'--actor','scripted-operator'],
                         input='6\n'+str(path)+'\n0\n',text=True,capture_output=True,check=True)
    assert 'Evidência exportada' in run.stdout
    report = json.loads(path.read_text())
    assert report['history']['result']['entries'] == []
    assert report['review_audit']['result']['receipts'] == []
