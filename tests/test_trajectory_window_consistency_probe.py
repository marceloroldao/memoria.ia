import copy
import hashlib
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_window_consistency_probe import (
    WindowChanged, window_snapshot, resolve_guarded_region, probe)


def rows():
    return [dict(hierarchy_id='conversation:a', source_id=source, sequence=sequence,
                 text=text, source_kind='user_turn', reply_to=target)
            for source, sequence, text, target in (
                ('q', 1, 'opaque query', None),
                ('a', 2, 'opaque value', dict(source_id='q', sequence=1)))]


class ModelNative:
    """Contract-shaped test double; native execution is a separate test."""
    def __init__(self, observations, mutation=None):
        self.rows, self.requests = copy.deepcopy(observations), []
        self.mutation = mutation

    def call(self, name, request):
        self.requests.append((name, copy.deepcopy(request)))
        if name == 'read_structural_window':
            region = request['hierarchy_id']
            local = sorted([r for r in self.rows if r['hierarchy_id'] == region],
                           key=lambda r: (r['sequence'], r['source_id']))
            token = hashlib.sha256(repr(local).encode()).hexdigest()[:16]
            if request.get('expected_token', token) != token:
                result = (2, dict(status='STALE_WINDOW', window_id=region,
                                  window_token=token, window_revision=len(local), observations=[]))
            else:
                offset, limit = request['offset'], request['limit']
                values = copy.deepcopy(local[offset:offset + limit])
                end = offset + len(values)
                result = (0, dict(status='OK', window_id=region, window_token=token,
                    window_revision=len(local), observations=values,
                    page=dict(offset=offset, returned=len(values),
                              next_offset=end if end < len(local) else None)))
        else:
            assert name == 'probe_structural_linked_replies'
            witnesses = []
            for item in self.rows:
                if not item['reply_to']:
                    continue
                target = next(r for r in self.rows if r['hierarchy_id'] == item['hierarchy_id']
                              and r['source_id'] == item['reply_to']['source_id']
                              and r['sequence'] == item['reply_to']['sequence'])
                if target['text'] != request['query']:
                    continue
                witnesses.append(dict(hierarchy_id=item['hierarchy_id'],
                    question=dict(source_id=target['source_id'], sequence=target['sequence'],
                                  source_kind=target['source_kind'], match='EXACT'),
                    reply=dict(source_id=item['source_id'], sequence=item['sequence'], text=item['text'],
                               source_kind=item['source_kind'], repeats_query=False, trail_address='test-trail')))
            offset, limit = request['offset'], request['limit']
            values = witnesses[offset:offset + limit]
            end = offset + len(values)
            result = (2, dict(qualified=False, selection_used=False, relation='reply_to',
                explicit_reply_occurrences=len(witnesses), distinct_reply_trails=1,
                embedded_question_links=0, repeat_question_links=0, witnesses=values,
                page=dict(offset=offset, returned=len(values),
                          next_offset=end if end < len(witnesses) else None)))
        if self.mutation:
            self.mutation(self, name, request, result[1])
        return result


class WindowConsistencyTests(unittest.TestCase):
    def test_complete_window_pages_keep_expected_token_and_reject_omissions(self):
        data = rows() + [dict(hierarchy_id='conversation:a', source_id=str(i), sequence=i,
                             text='opaque', source_kind='user_turn', reply_to=None) for i in range(3, 70)]
        native = ModelNative(data)
        snapshot = window_snapshot(native, 'conversation:a')
        self.assertEqual(len(snapshot['rows']), 69)
        self.assertNotIn('expected_token', native.requests[0][1])
        self.assertEqual(native.requests[1][1]['expected_token'], snapshot['token'])
        def omit(native, name, request, packet): packet['page']['next_offset'] = None
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            window_snapshot(ModelNative(data, omit), 'conversation:a')
        def duplicate(native, name, request, packet):
            if request['offset']: packet['observations'][0] = copy.deepcopy(data[0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            window_snapshot(ModelNative(data, duplicate), 'conversation:a')

    def test_mutation_during_row_pagination_is_rejected(self):
        data = rows() + [dict(hierarchy_id='conversation:a', source_id=str(i), sequence=i,
                             text='opaque', source_kind='user_turn', reply_to=None) for i in range(3, 70)]
        def append(native, name, request, packet):
            if request['offset'] == 0:
                native.rows.append(dict(data[-1], source_id='late', sequence=100))
        with self.assertRaises(WindowChanged):
            window_snapshot(ModelNative(data, append), 'conversation:a')

    def test_stale_caller_rows_rejected_before_any_witness_request(self):
        data = rows()
        native = ModelNative(data + [dict(data[0], source_id='late', sequence=3, reply_to=None)])
        result = resolve_guarded_region(native, data, 'conversation:a', 'opaque query')
        self.assertEqual(result['reason'], 'STALE_INPUT_ROWS')
        self.assertIsNone(result['view'])
        self.assertTrue(all(name == 'read_structural_window' for name, _ in native.requests))

    def test_same_header_local_append_after_last_page_returns_no_partial_view(self):
        data = rows()
        before = copy.deepcopy(data)
        def append(native, name, request, packet):
            if name == 'probe_structural_linked_replies':
                native.rows.append(dict(data[0], source_id='late', sequence=3, reply_to=None))
        result = resolve_guarded_region(ModelNative(data, append), data, 'conversation:a', 'opaque query', 1)
        self.assertEqual(result['reason'], 'STALE_REGIONAL_WINDOW')
        self.assertIsNone(result['view'])
        self.assertIsNone(result['answer'])
        self.assertFalse(result['qualified'])
        self.assertEqual(data, before)

    def test_foreign_append_keeps_local_boundary_and_labels_snapshot_provenance(self):
        data = rows()
        def append(native, name, request, packet):
            if name == 'probe_structural_linked_replies':
                native.rows.append(dict(data[0], hierarchy_id='conversation:b', reply_to=None))
        result = resolve_guarded_region(ModelNative(data, append), data, 'conversation:a', 'opaque query')
        self.assertEqual(result['status'], 'OK')
        self.assertFalse(result['consistency']['global_snapshot_guaranteed'])
        self.assertEqual(result['consistency']['foreign_provenance'], 'caller_supplied_rows')

    def test_absent_target_has_no_witness_request_and_invalid_limits_fail_early(self):
        native = ModelNative(rows())
        result = resolve_guarded_region(native, rows(), 'conversation:unknown', 'opaque query')
        self.assertEqual(result['status'], 'OK')
        self.assertFalse(result['view']['episodes'])
        self.assertTrue(all(name == 'read_structural_window' for name, _ in native.requests))
        for limit in (0, 65, True, '1'):
            invalid = ModelNative(rows())
            with self.assertRaises(ValueError):
                resolve_guarded_region(invalid, rows(), 'conversation:a', 'opaque query', limit)
            self.assertFalse(invalid.requests)

    def test_malformed_initial_or_postcheck_token_is_not_accepted(self):
        for when in ('initial', 'postcheck'):
            def forge(native, name, request, packet):
                if name == 'read_structural_window' and (when == 'initial' or 'expected_token' in request):
                    packet['window_token'] = 'invalid'
            with self.subTest(when=when), self.assertRaises(ValueError):
                resolve_guarded_region(ModelNative(rows(), forge), rows(), 'conversation:a', 'opaque query')

    @unittest.skipUnless(os.environ.get('MEMORIA_NATIVE_LIBRARY'), 'requires native BDR library')
    def test_real_native_interventions_and_cold_reopen(self):
        for seed in (20261209, 20261210):
            result = probe(Path(os.environ['MEMORIA_NATIVE_LIBRARY']), seed)
            self.assertEqual((result['integrity_passed'], result['integrity_total']), (72, 72))
            self.assertEqual(result['original_current_window_failures'], 4)
            self.assertEqual(len(result['cases']), 8)
            self.assertFalse(result['global_snapshot_guaranteed'])


if __name__ == '__main__':
    unittest.main()
