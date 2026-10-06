import copy
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_region_target_probe import enumerate_targets, resolve_region, probe


def rows():
    return [dict(hierarchy_id=scope, source_id=source, sequence=sequence,
                 text='opaque text', source_kind=kind, reply_to=None)
            for scope, source, sequence, kind in [
                ('conversation:a', 'first', 1, 'user_turn'),
                ('conversation:a', 'second', 2, 'user_assertion'),
                ('conversation:a', 'generated', 3, 'assistant_generated'),
                ('conversation:b', 'first', 1, 'user_turn')]]


class RecordingProbe:
    def __init__(self, **overrides):
        self.requests = []
        self.packet = dict(answer=None, qualified=False, selection_used=False,
                           evidence_scope='exact_target', groups=[], groups_truncated=False,
                           repeat_question_links=0, status='UNRESOLVED')
        self.packet.update(overrides)

    def call(self, name, request):
        self.requests.append((name, copy.deepcopy(request)))
        return 2, copy.deepcopy(self.packet)


class RegionTargetTests(unittest.TestCase):
    def test_raw_occurrences_are_not_deduplicated_or_question_classified(self):
        self.assertEqual(enumerate_targets(rows(), 'conversation:a', 'opaque text'),
                         [('conversation:a', 'first', 1), ('conversation:a', 'second', 2)])
        self.assertEqual(enumerate_targets(rows(), 'conversation:b', 'opaque text'),
                         [('conversation:b', 'first', 1)])

    def test_missing_scope_and_invalid_query_are_rejected(self):
        for region in (None, '', ' ', False, 42):
            with self.subTest(region=region), self.assertRaises(ValueError):
                enumerate_targets(rows(), region, 'opaque text')
        for query in (None, '', False, 42):
            with self.subTest(query=query), self.assertRaises(ValueError):
                enumerate_targets(rows(), 'conversation:a', query)
        duplicate = rows() + [rows()[0]]
        with self.assertRaises(ValueError):
            enumerate_targets(duplicate, 'conversation:a', 'opaque text')

    def test_all_native_calls_include_the_exact_local_address(self):
        native = RecordingProbe()
        result = resolve_region(native, rows(), 'conversation:a', 'opaque text')
        self.assertEqual(len(native.requests), 2)
        self.assertEqual(result['target_status'], 'AMBIGUOUS_RAW_MATCHES')
        self.assertIsNone(result['selected_target'])
        for (_, request), target in zip(native.requests, enumerate_targets(rows(), 'conversation:a', 'opaque text')):
            self.assertEqual((request['hierarchy_id'], request['target_source_id'], request['target_sequence']), target)
            self.assertEqual(request['mode'], 'linked_reply_evidence')
        single = resolve_region(RecordingProbe(), rows(), 'conversation:b', 'opaque text')
        self.assertEqual(single['target_status'], 'SINGLE_RAW_MATCH')
        self.assertIsNone(single['selected_target'])

    def test_absent_raw_match_makes_no_native_global_request(self):
        for region, query in [('conversation:missing', 'opaque text'),
                              ('conversation:a', 'prefix opaque text'),
                              ('conversation:a', 'OPAQUE TEXT')]:
            native = RecordingProbe()
            result = resolve_region(native, rows(), region, query)
            self.assertEqual(result['raw_target_count'], 0)
            self.assertEqual(native.requests, [])
            self.assertFalse(result['global_fallback_used'])

    def test_incomplete_echo_or_truncated_packet_is_visible_without_join(self):
        for overrides, expected in [({'repeat_question_links': 1}, 'UNSUPPORTED_QUERY_ECHO_LINKS'),
                                    ({'groups_truncated': True}, 'INCOMPLETE_NATIVE_EVIDENCE')]:
            native = RecordingProbe(**overrides)
            result = resolve_region(native, rows(), 'conversation:b', 'opaque text')
            self.assertEqual(result['episodes'][0]['join_status'], expected)
            self.assertIsNone(result['episodes'][0]['joined'])
            self.assertEqual(result['episodes'][0]['native_evidence'], native.packet)

    def test_qualified_or_global_native_contract_cannot_be_hidden(self):
        for overrides in ({'qualified': True}, {'answer': 'invented'},
                          {'evidence_scope': 'matching_targets'}, {'selection_used': True}):
            with self.subTest(overrides=overrides), self.assertRaises(RuntimeError):
                resolve_region(RecordingProbe(**overrides), rows(), 'conversation:b', 'opaque text')

    @unittest.skipUnless(os.environ.get('MEMORIA_NATIVE_LIBRARY'), 'requires native BDR library')
    def test_native_ambiguous_targets_unlinked_episode_echo_and_cold_reopen(self):
        for seed in (20261205, 20261206):
            with self.subTest(seed=seed):
                result = probe(Path(os.environ['MEMORIA_NATIVE_LIBRARY']), seed)
                self.assertEqual(result['integrity_passed'], 27)
                self.assertEqual(result['integrity_total'], 27)
                for stage in result['stages']:
                    local, foreign, missing, prefix = [c['result'] for c in stage['cases']]
                    self.assertEqual(local['raw_target_count'], 3)
                    self.assertEqual(foreign['raw_target_count'], 1)
                    self.assertEqual(missing['raw_target_count'], 0)
                    self.assertEqual(prefix['raw_target_count'], 0)
                    self.assertEqual(len(prefix['structural']['packet']['candidates']), 2)
                    self.assertFalse(prefix['episodes'])
                    self.assertIsNone(local['answer'])
                    self.assertFalse(local['qualified'])


if __name__ == '__main__':
    unittest.main()
