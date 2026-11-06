import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_feedback_console import ReviewJournal, assessment, run_console
from trajectory_feedback_lab import open_lab
from trajectory_region_evidence_probe import fingerprint
from trajectory_route_relation_probe import fixture


@pytest.fixture
def library():
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so')).resolve()
    if not library.exists():
        pytest.fail('Build the pinned native library before these native integration contracts')
    return library


def train(lab, case='same_root_two_routes'):
    rows, _, queries = fixture(case, 20270107)
    for row in rows:
        lab.execute(dict(op='observe', source_id=row['source_id'], text=row['text'],
                         source_kind=row['source_kind']))
    return next(q for q in queries if q['name'] == 'literal_cue')


def query(lab, question):
    return lab.execute(dict(op='query', text=question))


def feedback(lab, packet, index=0):
    return lab.execute(dict(op='feedback', receipt=packet['result']['receipts'][index],
                            actor_id='scripted-test', event_id='test-veto', stance='oppose'))


def test_assessments_do_not_train_or_apply_feedback_and_survive_reopen(library, tmp_path):
    path = tmp_path / 'operator-reviews.jsonl'
    with open_lab(library, tmp_path, enable_feedback=True) as lab:
        challenge = train(lab)
        packet = query(lab, challenge['text'])
        before = lab.execute(dict(op='history'))
        journal = ReviewJournal(path)
        review = assessment(challenge['text'], packet, challenge['expected'], 'scripted-test')
        journal.append(review)
        journal.append(assessment(challenge['text'], packet, [], 'scripted-test'))
        assert lab.execute(dict(op='history')) == before
        assert query(lab, challenge['text']) == packet
        report = journal.report()
        assert report['assessments'] == 2
        assert report['human_participation'] == 'NOT_VERIFIED'
        assert report['totals']['raw_score']['false_positive'] > 0
    with open_lab(library, tmp_path, enable_feedback=True) as lab:
        assert ReviewJournal(path).report() == report
        assert lab.execute(dict(op='history')) == before
        assert query(lab, challenge['text']) == packet


@pytest.mark.parametrize('case,expected_effect', [('partial_overlap', 'FEWER_ERRORS'),
                                                ('same_root_two_routes', 'MORE_ERRORS')])
def test_measure_correct_and_incorrect_veto_against_same_saved_read(library, tmp_path, case, expected_effect):
    with open_lab(library, tmp_path, enable_feedback=True) as lab:
        challenge = train(lab, case)
        packet = query(lab, challenge['text'])
        bindings = packet['result']['receipts']
        index = (next(i for i, b in enumerate(bindings)
                      if any(o[1] == 'added-map-target' for o in b['candidate']['origins']))
                 if case == 'partial_overlap' else 0)
        feedback(lab, packet, index)
        after = query(lab, challenge['text'])
        review = assessment(challenge['text'], after, challenge['expected'], 'scripted-test')
        assert review['effect'] == expected_effect
        assert review['extra_removed'] == (1 if case == 'partial_overlap' else 0)
        assert review['expected_removed'] == (0 if case == 'partial_overlap' else 1)
        lab.execute(dict(op='withdraw', event_id='test-veto', request_id='undo', actor_id='scripted-test'))
        restored = assessment(challenge['text'], query(lab, challenge['text']),
                              challenge['expected'], 'scripted-test')
        assert restored['effect'] == 'SAME_ERROR_COUNT'
        assert restored['raw_score'] == restored['filtered_score']


def test_empty_retrieval_records_missing_expected_without_creating_content(library, tmp_path):
    with open_lab(library, tmp_path) as lab:
        packet = query(lab, 'Pergunta sem observações?')
        before = lab.execute(dict(op='history'))
        review = assessment('Pergunta sem observações?', packet, ['Conteúdo ausente.'], 'scripted-test')
        assert review['filtered_score']['false_negative'] == 1
        assert review['raw_score']['false_negative'] == 1
        assert lab.execute(dict(op='history')) == before
        for expected in ('text', [7], ['x', 'x'], ['x' * 4097]):
            with pytest.raises(ValueError):
                assessment('Pergunta sem observações?', packet, expected, 'scripted-test')


@pytest.mark.parametrize('change', ['score', 'checksum', 'sequence', 'truncated'])
def test_journal_rejects_changed_or_partial_records(library, tmp_path, change):
    path = tmp_path / 'operator-reviews.jsonl'
    with open_lab(library, tmp_path) as lab:
        packet = query(lab, 'Vazia?')
        journal = ReviewJournal(path)
        entry = journal.append(assessment('Vazia?', packet, [], 'scripted-test'))
        altered = copy.deepcopy(entry)
        if change == 'score':
            altered['assessment']['raw_score']['false_positive'] = 999
            altered['sha256'] = fingerprint({k: v for k, v in altered.items() if k != 'sha256'})
        elif change == 'checksum':
            altered['sha256'] = 'bad'
        elif change == 'sequence':
            altered['sequence'] = 2
        path.write_text(json.dumps(altered) + ('' if change == 'truncated' else '\n'))
        before = path.read_bytes()
        with pytest.raises(ValueError):
            journal.report()
        assert path.read_bytes() == before


def test_prompted_console_uses_numbered_exact_receipts_and_requires_fresh_query(library, tmp_path):
    with open_lab(library, tmp_path, enable_feedback=True) as lab:
        challenge = train(lab)
        answers = iter(['2', challenge['text'], '4', '1', '7', '2', challenge['text'],
                        '7', json.dumps(challenge['expected']), '8', '0'])
        output = []
        journal = ReviewJournal(tmp_path / 'operator-reviews.jsonl')
        run_console(lab, journal, 'scripted-test', ask=lambda _: next(answers), show=output.append)
        assert any('[DISPONÍVEL]' in line for line in output)
        assert any('[VETADA]' in line for line in output)
        assert any('nova consulta antes de avaliar' in line for line in output)
        assert journal.report()['effects']['MORE_ERRORS'] == 1
        assert len(lab.execute(dict(op='history'))['result']['feedback']) == 1


def test_console_cli_restart_retains_reviews_without_native_learning(library, tmp_path):
    command = [sys.executable, 'scripts/trajectory_feedback_console.py', '--library', str(library),
               '--data-dir', str(tmp_path), '--actor', 'scripted-test']
    completed = subprocess.run(command, input='2\nVazia?\n7\n["Ausente."]\n8\n0\n',
                               text=True, capture_output=True, check=True)
    assert 'nenhum feedback ou aprendizado foi aplicado' in completed.stdout
    before = ReviewJournal(tmp_path / 'operator-reviews.jsonl').report()
    completed = subprocess.run(command, input='8\n0\n', text=True, capture_output=True, check=True)
    assert '"assessments": 1' in completed.stdout
    assert ReviewJournal(tmp_path / 'operator-reviews.jsonl').report() == before
    with open_lab(library, tmp_path) as lab:
        assert lab.execute(dict(op='history'))['result']['entries'] == []
