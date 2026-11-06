import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_transform_catalogue_probe import ARMS, CATALOGUES, EXPERIMENTS, fixture_for, probe


def test_new_catalogue_interventions_preserve_prefix_and_exclude_targets():
    for catalogue in CATALOGUES:
        for experiment in EXPERIMENTS:
            baseline = fixture_for(catalogue,experiment,'baseline')
            targets = set(baseline['queries'][0]['expected'])
            target_query = baseline['queries'][0]['text']
            for arm in ARMS:
                fixture = fixture_for(catalogue,experiment,arm)
                assert fixture['rows'][:len(baseline['rows'])] == baseline['rows']
                added = fixture['rows'][fixture['intervention_start']:]
                assert not targets.intersection(r['text'] for r in added)
                assert target_query not in {r['text'] for r in added}
                assert all(set(r) <= {'event_id','text','source_kind'} for r in added)
                assert fixture['queries'] == baseline['queries']


def test_ambiguous_reference_retains_two_observed_payloads_without_truth_label():
    for catalogue in CATALOGUES:
        fixture = fixture_for(catalogue,'conflicting_map','intervention')
        expected = fixture['queries'][0]['expected']
        assert len(set(expected)) == 2
        assert set(expected) <= {r['text'] for r in fixture['rows']}
        assert all(not q['expected'] for q in fixture['queries'][1:])


def test_native_new_catalogues_preserve_controls_and_competing_routes():
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    report = probe(library)
    assert report['integrity_status'] == 'PASS' and all(report['checks'].values())
    for catalogue in CATALOGUES:
        for experiment in EXPERIMENTS:
            summary = report['summary'][catalogue][experiment]
            assert summary['baseline'] == summary['irrelevant'] == summary['contrast']
            assert summary['intervention']['exact'] and summary['intervention']['extra']==0
            assert summary['intervention']['recovered'] > summary['baseline']['recovered']
    for trial in report['trials']:
        if trial['experiment']=='sensitive_ids':
            assert all(c['score']['exact'] for c in trial['cases'])
            continue
        assert all(c['score']['exact'] for c in trial['cases'][1:])
        primary = trial['cases'][0]['view']
        assert primary['answer'] is None and not primary['qualified'] and not primary['selection_used']
        if trial['experiment']=='conflicting_map' and trial['arm']=='intervention':
            assert len(primary['result']['available_candidates'])==2
            assert primary['result']['selected_target'] is None
