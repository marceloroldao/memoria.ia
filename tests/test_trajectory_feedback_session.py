import os
from pathlib import Path
import sys
import json
import subprocess

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_feedback_session import FeedbackSession
from trajectory_route_relation_probe import fixture


@pytest.fixture
def session(tmp_path):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists():
        pytest.skip('native library required')
    with FeedbackSession(library, tmp_path / 'session') as active:
        yield active, library, tmp_path / 'session'


def populate(active):
    rows, _, queries = fixture('same_root_two_routes', 20270107)
    for row in rows:
        active.execute(dict(op='observe', event_id=row['source_id'], text=row['text'], source_kind=row['source_kind']))
    return next(q['text'] for q in queries if q['name'] == 'literal_cue')


def test_complete_cycle_survives_process_restart(session):
    active, library, directory = session
    query = populate(active)
    before = active.execute(dict(op='query', text=query))
    binding = before['result']['receipts'][0]
    feedback = dict(op='feedback', receipt=binding, event_id='opposition', actor_id='operator', stance='oppose')
    target = active.execute(feedback)['result']
    target = {k: target[k] for k in ('address', 'event')}
    assert active.execute(dict(op='query', text=query))['result']['withheld_candidates']
    # An unrelated append changes the snapshot; the single reader applies continuity.
    active.execute(dict(op='observe', event_id='later', text='Observação posterior.'))
    assert active.execute(dict(op='query', text=query))['result']['withheld_candidates']
    withdrawal = dict(op='withdraw', request_id='withdraw', actor_id='operator', target=target)
    active.execute(withdrawal)
    after = active.execute(dict(op='query', text=query))
    assert not after['result']['withheld_candidates']
    assert after['result']['raw_view'] == before['result']['raw_view']
    assert active.execute(feedback)['result']['status'] == 'EXACT_REPLAY'
    assert active.execute(withdrawal)['result']['status'] == 'EXACT_REPLAY'
    history = active.execute(dict(op='history'))
    assert not history['result']['feedback_projection'][0]['active']
    assert len(history['result']['withdrawal_history']) == 1
    active.close()
    with FeedbackSession(library, directory) as cold:
        assert cold.execute(dict(op='query', text=query)) == after
        assert cold.execute(dict(op='history')) == history
        assert cold.execute(feedback)['result']['status'] == 'EXACT_REPLAY'
        assert cold.execute(withdrawal)['result']['status'] == 'EXACT_REPLAY'


def test_scope_and_stale_feedback_reject_without_writes(session):
    active, _, _ = session
    query = populate(active)
    binding = active.execute(dict(op='query', text=query))['result']['receipts'][0]
    command = dict(op='feedback', receipt=binding, event_id='feedback', actor_id='operator', stance='oppose')
    with pytest.raises(ValueError, match='scope'):
        active.execute(dict(command, scope='foreign'))
    active.execute(dict(op='observe', event_id='later', text='Observação posterior.'))
    saved = active.execute(dict(op='history'))
    with pytest.raises(ValueError, match='stale'):
        active.execute(command)
    assert active.execute(dict(op='history')) == saved


def test_observation_retry_conflict_and_excluded_generated_content(session):
    active, _, _ = session
    command = dict(op='observe', event_id='one', text='Meu gato é Alt.')
    active.execute(command)
    assert active.execute(command)['result']['status'] == 'EXACT_REPLAY'
    with pytest.raises(ValueError, match='identity reused'):
        active.execute(dict(command, text='Meu gato é Outro.'))
    active.execute(dict(op='observe', event_id='generated', text='Meu gato é Nino.', source_kind='assistant_generated'))
    before = active.execute(dict(op='history'))
    view = active.execute(dict(op='query', text='Meu gato é Nino.'))
    assert all(c['text'] != 'Meu gato é Nino.' for c in view['result']['raw_view']['candidates'])
    assert active.execute(dict(op='history')) == before
    assert not view['qualified'] and view['answer'] is None and not view['selection_used']
    assert view['result']['query_recorded'] is False


def test_directory_lock_blocks_second_writer(session):
    _, library, directory = session
    with pytest.raises(BlockingIOError):
        FeedbackSession(library, directory)


def test_terminal_protocol_rejects_bad_line_and_persists_after_exit(session, tmp_path):
    _, library, _ = session
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'trajectory_feedback_session.py'
    directory = tmp_path / 'terminal'
    commands = ['invalid-json', json.dumps(dict(op='observe', event_id='one', text='Texto observado.')),
                json.dumps(dict(op='history'))]
    run = subprocess.run([sys.executable, str(script), '--library', str(library.resolve()),
                          '--data-dir', str(directory)], input='\n'.join(commands)+'\n',
                         text=True, capture_output=True, check=True)
    outputs = [json.loads(line) for line in run.stdout.splitlines()]
    assert len(outputs) == 3 and outputs[0]['status'] == 'REJECTED'
    assert outputs[1]['result']['persisted']
    with FeedbackSession(library, directory) as cold:
        assert cold.execute(dict(op='history')) == outputs[2]


@pytest.mark.parametrize('command', [
    {'op': 'history', 'scope': 'feedback-ledger:x'},
    {'op': 'history', 'enabled': False},
    {'op': 'observe', 'event_id': 'x', 'text': ' '},
    {'op': 'query', 'text': ' '},
    {'op': 'observe', 'event_id': 'x', 'text': 'x' * 4097},
])
def test_invalid_commands_do_not_write(session, command):
    active, _, _ = session
    before = active.execute(dict(op='history'))
    with pytest.raises(ValueError):
        active.execute(command)
    assert active.execute(dict(op='history')) == before
