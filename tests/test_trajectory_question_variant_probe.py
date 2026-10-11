import os
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_question_variant_probe import fixture
from trajectory_question_frame_probe import read, trial


def view(case, name):
    rows, region, queries = fixture(case, 20261223)
    query = next(q for q in queries if q['name'] == name)
    result = read(rows, region, query['text'])
    return {c['text'] for c in result['candidates']}, result, query, rows


def test_observed_variants_recover_new_entity_but_not_unseen_wording_or_case_conversion():
    for name in ('paraphrase', 'uppercase_cue'):
        texts, result, query, rows = view('observed_variants', name)
        assert texts == set(query['expected'])
        assert query['text'] not in {r['text'] for r in rows}
        assert result['answer'] is None and not result['qualified']
        assert not view('baseline', name)[0]
    assert not view('observed_variants', 'uppercase')[0]
    assert not view('observed_variants', 'unseen_paraphrase')[0]
    texts, _, query, _ = view('matching_uppercase_targets', 'uppercase')
    assert texts == set(query['expected']) == {'A COR DO DRONE É VERDE.'}


def test_insufficient_foreign_and_generated_variants_do_not_supply_new_coverage():
    for case in ('two_examples', 'foreign_examples', 'generated_examples'):
        assert not view(case, 'paraphrase')[0]
        assert not view(case, 'uppercase_cue')[0]


def test_absence_controls_and_conflict_do_not_create_or_choose_facts():
    for name in ('age', 'current_absent', 'entity_absent', 'paraphrase_absent_entity', 'uppercase_absent_attribute'):
        assert not view('observed_variants', name)[0]
    for name in ('paraphrase', 'uppercase_cue'):
        texts, result, _, _ = view('repeated_conflict', name)
        assert texts == {'A cor do drone é verde.', 'A cor do drone é branca.'}
        assert sorted(len(c['origins']) for c in result['candidates']) == [1,20]
        assert result['proposal_payload_id'] is None and not result['selection_used']


def test_wrong_teaching_and_hidden_relevance_failures_remain_visible():
    assert view('crossed_paraphrase', 'paraphrase')[0] == {'O nome do drone é Nova.'}
    positive = view('observed_variants', 'paraphrase')
    twin = view('unrelated_twin', 'paraphrase')
    assert positive[1] == twin[1] and positive[3] == twin[3]
    assert positive[2]['expected'] and not twin[2]['expected']


@pytest.mark.skipif(not os.environ.get('MEMORIA_NATIVE_LIBRARY'), reason='requires native BDR library')
def test_native_cold_raw_and_full_view_parity():
    result = trial(Path(os.environ['MEMORIA_NATIVE_LIBRARY']), 'observed_variants', 20261223, False, fixture)
    assert all(result['checks'].values())
    allowed = {(r['hierarchy_id'],r['source_id'],r['sequence']) for r in result['rows'] if r['source_kind'] == 'user_turn'}
    assert all(tuple(o) in allowed for p in result['root_provenance'].values() for o in p['origins'])


def test_reserved_fixture_changes_lexical_values_without_changing_reader():
    rows, region, queries = fixture('observed_variants', 20261224)
    query = next(q for q in queries if q['name'] == 'paraphrase')
    assert query['text'] == 'Que cor tem o robô?'
    result = read(rows, region, query['text'])
    assert {c['text'] for c in result['candidates']} == set(query['expected']) == {'A cor do robô é laranja.'}
    assert query['text'] not in {r['text'] for r in rows}
