import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import trajectory_transfer_evaluation as evaluation


@pytest.mark.parametrize('domain',evaluation.DOMAINS)
@pytest.mark.parametrize('seed',evaluation.SEEDS)
def test_evaluation_questions_and_targets_are_excluded_from_additional_demonstrations(domain,seed):
    base = evaluation.fixture(domain,seed,'baseline')
    questions = {q['text'] for q in base['queries']}
    targets = {text for q in base['queries'] for text in q['expected']}
    for arm in evaluation.ARMS:
        fixture = evaluation.fixture(domain,seed,arm)
        assert fixture['rows'][:len(base['rows'])] == base['rows']
        assert fixture['queries'] == base['queries']
        assert questions.isdisjoint(row['text'] for row in fixture['rows'])
        assert targets.isdisjoint(row['text'] for row in fixture['rows'][fixture['intervention_start']:])
        assert targets <= {row['text'] for row in base['rows'] if row['source_kind']=='user_turn'}
        assert all(set(row)=={'event_id','text','source_kind'} for row in fixture['rows'])
    teaching = evaluation.fixture(domain,seed,'intervention')['rows'][-3:]
    wrong = evaluation.fixture(domain,seed,'contrast')['rows'][-3:]
    assert teaching[0] == wrong[0] and teaching[2] == wrong[2]
    assert teaching[1]['text'] != wrong[1]['text']


@pytest.mark.parametrize('arm',['contrast','intervention'])
def test_native_transfer_commands_do_not_contain_references_or_reinsert_queries(arm,monkeypatch):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    commands = []; original = evaluation.FeedbackSession.execute
    def capture(self, command):
        commands.append(dict(command))
        return original(self,command)
    monkeypatch.setattr(evaluation.FeedbackSession,'execute',capture)
    fixture = evaluation.fixture('humidity',evaluation.SEEDS[0],arm)
    trial = evaluation.trial(library,fixture)
    assert all(trial['checks'].values())
    assert all('expected' not in command and 'score' not in command for command in commands)
    observed = [command['text'] for command in commands if command['op']=='observe']
    assert observed == [r['text'] for r in fixture['rows']]+[fixture['foreign']]
    assert all(case['answer'] is None and not case['qualified'] for case in trial['cases'])


def test_strict_mode_rejects_incomplete_retrieval_despite_integrity_pass(tmp_path,monkeypatch):
    report = dict(integrity_status='PASS',retrieval_status='EXTRA_OR_MISSING_CONTENT',
                  required_retrieval_status='PASS_CURATED_REQUIRED_SET',summary={},
                  required_exact=28,required_total=28,selected_answer_count=0)
    monkeypatch.setattr(evaluation,'probe',lambda library:dict(report))
    args = ['probe','--library','unused','--output',str(tmp_path/'report.json')]
    monkeypatch.setattr(sys,'argv',args)
    assert evaluation.main() == 0
    monkeypatch.setattr(sys,'argv',args+['--strict-retrieval'])
    assert evaluation.main() == 1
