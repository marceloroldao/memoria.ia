import copy
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_bounded_refresh_probe import resolve_with_refresh, replace_region, probe
from test_trajectory_window_consistency_probe import ModelNative, rows


class BoundedRefreshTests(unittest.TestCase):
    def test_invalid_budget_and_limit_do_not_issue_native_requests(self):
        for key, values in [('max_attempts', (0, 9, True, 1.5, '2')),
                            ('limit', (0, 65, True, '1'))]:
            for value in values:
                native = ModelNative(rows())
                args = dict(max_attempts=2, limit=1)
                args[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    resolve_with_refresh(native, rows(), 'conversation:a', 'opaque query', **args)
                self.assertFalse(native.requests)

    def test_stale_input_refreshes_only_requested_region_and_keeps_rejection(self):
        data = rows() + [dict(rows()[0], hierarchy_id='conversation:b', reply_to=None)]
        original = copy.deepcopy(data)
        late = dict(rows()[0], source_id='late', sequence=3, reply_to=None)
        result = resolve_with_refresh(ModelNative(data + [late]), data,
                                      'conversation:a', 'opaque query', max_attempts=2, limit=1)
        self.assertEqual(result['status'], 'OK')
        self.assertEqual(result['attempts_used'], 2)
        self.assertEqual(result['attempts'][0]['reason'], 'STALE_INPUT_ROWS')
        self.assertEqual(result['attempts'][1]['refreshed_window']['revision'], 3)
        self.assertEqual(len(result['outcome']['view']['episodes']), 2)
        self.assertEqual(len({a['foreign_rows_sha256'] for a in result['attempts']}), 1)
        self.assertEqual(data, original)

    def test_isolated_write_recovers_on_second_attempt_without_erasing_history(self):
        fired = []
        def append(native, name, request, packet):
            if name == 'probe_structural_linked_replies' and not fired:
                native.rows.append(dict(rows()[0], source_id='late', sequence=3, reply_to=None))
                fired.append(True)
        result = resolve_with_refresh(ModelNative(rows(), append), rows(),
                                      'conversation:a', 'opaque query', max_attempts=2, limit=1)
        self.assertEqual(result['status'], 'OK')
        self.assertEqual([a['status'] for a in result['attempts']], ['REJECTED', 'OK'])
        self.assertEqual(result['attempts'][0]['reason'], 'STALE_REGIONAL_WINDOW')
        self.assertNotEqual(result['attempts'][0]['input_rows_sha256'], result['attempts'][1]['input_rows_sha256'])

    def test_continuous_writes_exhaust_exact_budget_and_expose_no_view(self):
        writes = []
        def append(native, name, request, packet):
            if name == 'probe_structural_linked_replies':
                sequence = 10 + len(writes)
                native.rows.append(dict(rows()[0], source_id=str(sequence), sequence=sequence, reply_to=None))
                writes.append(sequence)
        result = resolve_with_refresh(ModelNative(rows(), append), rows(),
                                      'conversation:a', 'opaque query', max_attempts=3, limit=1)
        self.assertEqual(result['status'], 'EXHAUSTED')
        self.assertEqual(result['attempts_used'], 3)
        self.assertEqual(len(writes), 3)
        self.assertIsNone(result['outcome']['view'])
        self.assertIsNone(result['answer'])
        self.assertFalse(result['qualified'])
        self.assertTrue(all(a['reason'] == 'STALE_REGIONAL_WINDOW' for a in result['attempts']))

    def test_qualified_witness_contract_is_terminal_without_refresh_retry(self):
        def qualify(native, name, request, packet):
            if name == 'probe_structural_linked_replies': packet['qualified'] = True
        native = ModelNative(rows(), qualify)
        result = resolve_with_refresh(native, rows(), 'conversation:a', 'opaque query', max_attempts=8)
        self.assertEqual(result['status'], 'REJECTED')
        self.assertEqual(result['attempts_used'], 1)
        self.assertEqual(result['attempts'][0]['reason'], 'WITNESS_CONTRACT_REJECTED')
        self.assertIsNone(result['outcome']['view'])
        self.assertEqual(sum(name == 'read_structural_window' for name, _ in native.requests), 1)

    def test_stale_refresh_page_spends_attempt_before_success(self):
        data = rows() + [dict(rows()[0], source_id=str(i), sequence=i, text='opaque', reply_to=None)
                         for i in range(3, 68)]
        stage = []
        def append(native, name, request, packet):
            if name == 'probe_structural_linked_replies' and not stage:
                native.rows.append(dict(rows()[0], source_id='late-100', sequence=100, reply_to=None))
                stage.append('initial')
            elif (stage == ['initial'] and name == 'read_structural_window'
                  and request['limit'] == 64 and request['offset'] == 0 and 'expected_token' not in request):
                native.rows.append(dict(rows()[0], source_id='late-101', sequence=101, reply_to=None))
                stage.append('refresh')
        result = resolve_with_refresh(ModelNative(data, append), data,
                                      'conversation:a', 'opaque query', max_attempts=3)
        self.assertEqual(result['status'], 'OK')
        self.assertEqual([a['phase'] for a in result['attempts']], ['resolve', 'refresh', 'resolve'])
        self.assertEqual([a['status'] for a in result['attempts']], ['REJECTED', 'REJECTED', 'OK'])
        self.assertEqual(result['attempts_used'], 3)

    def test_region_replacement_preserves_foreign_order_and_absent_target_has_no_witness_calls(self):
        data = [dict(rows()[0], hierarchy_id='conversation:b'), *rows(),
                dict(rows()[0], hierarchy_id='conversation:c')]
        changed = replace_region(data, 'conversation:a', [dict(rows()[0], source_id='replacement')])
        self.assertEqual([r['hierarchy_id'] for r in changed], ['conversation:b', 'conversation:a', 'conversation:c'])
        self.assertEqual(changed[0], data[0])
        self.assertEqual(changed[-1], data[-1])
        native = ModelNative(rows())
        result = resolve_with_refresh(native, rows(), 'conversation:unknown', 'opaque query', max_attempts=3)
        self.assertEqual(result['status'], 'OK')
        self.assertEqual(result['attempts_used'], 1)
        self.assertTrue(all(name == 'read_structural_window' for name, _ in native.requests))

    @unittest.skipUnless(os.environ.get('MEMORIA_NATIVE_LIBRARY'), 'requires native BDR library')
    def test_native_budgets_interventions_and_cold_reopen(self):
        for seed in (20261211, 20261212):
            result = probe(Path(os.environ['MEMORIA_NATIVE_LIBRARY']), seed)
            self.assertEqual((result['integrity_passed'], result['integrity_total']), (90, 90))
            self.assertEqual(len(result['cases']), 10)
            self.assertFalse(result['global_snapshot_guaranteed'])


if __name__ == '__main__':
    unittest.main()
