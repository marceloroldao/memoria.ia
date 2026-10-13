import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_feedback_portuguese_probe import fixtures, probe


def test_curated_inputs_keep_evaluator_references_out_of_observations():
    data = fixtures()
    assert len(data) == 4 and sum(len(f['queries']) for f in data) == 32
    assert all(set(row) <= {'event_id', 'text', 'source_kind'} for f in data for row in f['rows'])
    assert all(not q['expected'] for f in data for q in f['queries'][3:])


def test_native_portuguese_probe_preserves_quality_failures_and_cold_views():
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists():
        pytest.skip('native library required')
    report = probe(library)
    assert report['integrity_status'] == 'PASS' and all(report['checks'].values())
    assert report['human_evaluation_status'] == 'NOT_PERFORMED'
    assert report['general_learning_status'] == 'NOT_ESTABLISHED'
    assert report['retrieval_status'] == 'EXTRA_OR_MISSING_CONTENT'
    assert report['totals']['missing'] > 0
    cycles = [c['feedback_cycle'] for c in report['cases'][::8]]
    assert any(c['status'] == 'SCRIPTED_CYCLE_EXECUTED' for c in cycles)
    assert all(c['before'] == c['restored'] for c in cycles if c['status'] == 'SCRIPTED_CYCLE_EXECUTED')
