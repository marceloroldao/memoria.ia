import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_feedback_case_probe import ARMS, case_question, diagnostic_fixture, sensitive_fixture
from trajectory_feedback_variants_probe import corpus, evaluate


def test_case_changes_are_local_and_do_not_normalize_output():
    question = 'Qual é o nome do Coelho?'
    assert case_question(question, 'fixed') == 'QUAL É O NOME DO Coelho?'
    assert case_question(question, 'entity') == 'Qual é o nome do COELHO?'
    assert case_question(question, 'full') == 'QUAL É O NOME DO COELHO?'
    assert case_question(question, 'baseline') == question


def test_diagnostic_labels_and_target_questions_never_enter_demonstrations():
    for split in ('development','reserved'):
        for base in corpus(split):
            for arm in ARMS:
                fixture, coverage = diagnostic_fixture(base, arm)
                added = fixture['rows'][len(base['rows']):]
                assert all(set(r) <= {'event_id','text','source_kind'} for r in added)
                assert not {q['text'] for q in fixture['queries'][:4]}.intersection(r['text'] for r in added)
                assert coverage['evaluator_only']
                assert set(map(tuple,coverage['unwitnessed_case_pairs'])) == set(map(tuple,coverage['required_case_pairs']))-set(map(tuple,coverage['observed_case_pairs']))


def test_case_sensitive_identifiers_have_distinct_reference_roots():
    fixture = sensitive_fixture()
    assert fixture['queries'][0]['expected'] != fixture['queries'][1]['expected']
    assert fixture['queries'][0]['text'].upper() == fixture['queries'][1]['text'].upper()


@pytest.mark.parametrize('arm',ARMS)
def test_native_case_ablation_reopens_without_mutation(arm):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    fixture, _ = diagnostic_fixture(corpus('development')[0], arm)
    trial = evaluate(library,'development','baseline',fixture)
    assert all(trial['checks'].values())
    assert all(c['score']['extra'] == 0 for c in trial['cases'][4:])
