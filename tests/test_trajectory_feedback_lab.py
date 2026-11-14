import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_feedback_lab import open_lab, serve
from trajectory_route_relation_probe import fixture


@pytest.fixture
def library():
    path = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so')).resolve()
    if not path.exists():
        if 'MEMORIA_NATIVE_LIBRARY' in os.environ:
            pytest.fail('Explicit native BDR library is missing')
        pytest.skip('Native integration runs in the dedicated pinned-BDR job')
    return path


def train(lab, case='same_root_two_routes', seed=20270107):
    rows, _, queries = fixture(case, seed)
    for row in rows:
        lab.execute(dict(op='observe', source_id=row['source_id'],
                         text=row['text'], source_kind=row['source_kind']))
    return next(q['text'] for q in queries if q['name'] == 'literal_cue')


def query(lab, text):
    return lab.execute(dict(op='query', text=text))['result']


def oppose(lab, binding, event_id='oppose', actor='operator'):
    return lab.execute(dict(op='feedback', receipt=binding, event_id=event_id,
                            actor_id=actor, stance='oppose'))


def undo(lab, event_id='oppose', request_id='undo', actor='operator'):
    return lab.execute(dict(op='withdraw', event_id=event_id,
                            request_id=request_id, actor_id=actor))


def test_full_cycle_cold_reopen_and_exact_retries(library, tmp_path):
    with open_lab(library, tmp_path, enable_feedback=True) as lab:
        question = train(lab)
        before = lab.execute(dict(op='history'))['result']
        first = query(lab, question)
        assert first['receipts'] and first['view']['available_candidates']
        assert lab.execute(dict(op='history'))['result'] == before
        binding = first['receipts'][0]
        oppose(lab, binding)
        lab.execute(dict(op='observe', source_id='later', text='Observação posterior.'))
        assert query(lab, question)['view']['withheld_candidates']
    with open_lab(library, tmp_path, enable_feedback=True) as lab:
        assert query(lab, question)['view']['withheld_candidates']
        undo(lab)
        restored = query(lab, question)
        assert not restored['view']['withheld_candidates']
        assert restored['view']['raw_view'] == first['view']['raw_view']
        assert oppose(lab, binding)['result']['status'] == 'EXACT_REPLAY'
        assert undo(lab)['result']['status'] == 'EXACT_REPLAY'
        history = lab.execute(dict(op='history'))['result']
        assert len(history['feedback']) == len(history['withdrawals']) == 1
        assert not history['feedback'][0]['active']
        assert not query(lab, question)['view']['withheld_candidates']
    with open_lab(library, tmp_path, enable_feedback=True) as lab:
        assert query(lab, question) == restored
        assert lab.execute(dict(op='history'))['result'] == history


def test_other_opposition_and_new_feedback_remain_independent(library, tmp_path):
    with open_lab(library, tmp_path, enable_feedback=True) as lab:
        question = train(lab)
        binding = query(lab, question)['receipts'][0]
        oppose(lab, binding)
        oppose(lab, binding, 'other', 'other-operator')
        undo(lab)
        assert query(lab, question)['view']['withheld_candidates']
        undo(lab, 'other', 'undo-other', 'other-operator')
        assert not query(lab, question)['view']['withheld_candidates']
        oppose(lab, binding, 'new')
        assert query(lab, question)['view']['withheld_candidates']


def test_wrong_withdrawal_restores_extra_and_never_qualifies(library, tmp_path):
    with open_lab(library, tmp_path, enable_feedback=True) as lab:
        question = train(lab, 'partial_overlap')
        before = query(lab, question)
        binding = next(b for b in before['receipts'] if any(o[1] == 'added-map-target' for o in b['candidate']['origins']))
        oppose(lab, binding)
        assert len(query(lab, question)['view']['available_candidates']) < len(before['view']['available_candidates'])
        undo(lab)
        restored = lab.execute(dict(op='query', text=question))
        assert restored['result']['view']['available_candidates'] == before['view']['available_candidates']
        assert restored['answer'] is None and not restored['qualified']
        assert restored['result']['view']['answer'] is None


def test_disabled_policy_and_scope_isolation(library, tmp_path):
    with open_lab(library, tmp_path) as lab:
        question = train(lab)
        binding = query(lab, question)['receipts'][0]
        with pytest.raises(ValueError, match='disabled'):
            oppose(lab, binding)
    with open_lab(library, tmp_path, enable_feedback=True) as lab:
        oppose(lab, binding)
        with pytest.raises(ValueError, match='scope mismatch'):
            lab.execute(dict(op='feedback', scope='other', receipt=binding,
                             event_id='foreign', actor_id='operator', stance='oppose'))
        with pytest.raises(ValueError, match='not found'):
            lab.execute(dict(op='withdraw', scope='other', event_id='oppose',
                             request_id='foreign', actor_id='operator'))
        assert not lab.execute(dict(op='history', scope='other'))['result']['entries']
    with open_lab(library, tmp_path) as lab:
        assert not query(lab, question)['view']['withheld_candidates']
        assert lab.execute(dict(op='history'))['result']['feedback'][0]['active']


def test_rejections_preserve_history_and_observation_retry(library, tmp_path):
    with open_lab(library, tmp_path, enable_feedback=True) as lab:
        question = train(lab)
        binding = query(lab, question)['receipts'][0]
        oppose(lab, binding)
        history = lab.execute(dict(op='history'))
        altered = copy.deepcopy(binding)
        altered['query'] += '!'
        for command in (
            dict(op='feedback', receipt=altered, event_id='bad', actor_id='operator', stance='oppose'),
            dict(op='withdraw', event_id='oppose', request_id='bad', actor_id='impostor'),
            dict(op='observe', source_id='later', text='x', unexpected=True),
            dict(op='observe', source_id='later', text='x', scope='feedback-ledger:escape'),
        ):
            with pytest.raises(ValueError):
                lab.execute(command)
            assert lab.execute(dict(op='history')) == history
        row = history['result']['entries'][0]
        assert lab.execute(dict(op='observe', source_id=row['source_id'], text=row['text'],
                                source_kind=row['source_kind']))['result']['status'] == 'EXACT_REPLAY'
        with pytest.raises(ValueError, match='reused'):
            lab.execute(dict(op='observe', source_id=row['source_id'], text='changed'))
        lab.execute(dict(op='observe', source_id='later', text='Later.'))
        with pytest.raises(ValueError, match='stale'):
            oppose(lab, binding, 'stale')


def test_generated_isolation_limits_and_process_lock(library, tmp_path):
    with open_lab(library, tmp_path) as lab:
        lab.execute(dict(op='observe', source_id='generated', text='Secret generated only.',
                         source_kind='assistant_generated'))
        assert not query(lab, 'Secret generated only.')['view']['raw_view']['candidates']
        with pytest.raises(BlockingIOError):
            with open_lab(library, tmp_path):
                pass
        lab.execute(dict(op='observe', source_id='full', text='z' * (4096 - len('Secret generated only.'))))
        with pytest.raises(ValueError, match='limit'):
            lab.execute(dict(op='observe', source_id='overflow', text='x'))


def test_jsonl_errors_continue_without_writes(library, tmp_path):
    with open_lab(library, tmp_path) as lab:
        output = io.StringIO()
        serve(lab, io.StringIO('not json\n[]\n{"op":"history"}\n'), output)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        assert [r['ok'] for r in responses] == [False, False, True]
        assert responses[-1]['result']['entries'] == []


def test_cli_separate_process_restart(library, tmp_path):
    command = [sys.executable, 'scripts/trajectory_feedback_lab.py', '--library', str(library),
               '--data-dir', str(tmp_path), '--enable-feedback']
    def run(commands):
        completed = subprocess.run(command, input=''.join(json.dumps(c) + '\n' for c in commands),
                                   text=True, capture_output=True, check=True)
        return [json.loads(line) for line in completed.stdout.splitlines()]
    rows, _, queries = fixture('same_root_two_routes', 20270107)
    question = next(q['text'] for q in queries if q['name'] == 'literal_cue')
    initial = run([dict(op='observe', source_id=r['source_id'], text=r['text'], source_kind=r['source_kind'])
                   for r in rows] + [dict(op='query', text=question)])
    assert all(r['ok'] for r in initial)
    binding = initial[-1]['result']['receipts'][0]
    blocked = run([dict(op='feedback', receipt=binding, event_id='bad-veto', actor_id='human', stance='oppose'),
                   dict(op='query', text=question)])
    assert blocked[-1]['result']['view']['withheld_candidates']
    restored = run([dict(op='withdraw', event_id='bad-veto', request_id='undo', actor_id='human'),
                    dict(op='query', text=question), dict(op='history')])
    assert all(r['ok'] for r in restored)
    assert not restored[1]['result']['view']['withheld_candidates']
    assert restored[1]['result']['view']['raw_view'] == initial[-1]['result']['view']['raw_view']
    assert run([dict(op='history')])[0] == restored[-1]
