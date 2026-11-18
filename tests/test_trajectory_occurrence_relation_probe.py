import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_occurrence_relation_probe import fixtures, probe, relation_flags
from trajectory_native_evidence_join_probe import adapt_regions


class OccurrenceRelationTests(unittest.TestCase):
    def test_identical_payload_has_distinct_complete_origins(self):
        rows = [dict(hierarchy_id=scope, source_id='same', sequence=sequence,
                     text='same-content', source_kind='user_turn')
                for scope, sequence in [('conversation:a', 1), ('conversation:a', 2),
                                         ('conversation:b', 1)]]
        memory, origins = adapt_regions(rows)
        self.assertEqual(len(origins), 1)
        self.assertEqual(len(next(iter(origins.values()))), 3)
        self.assertEqual(len(memory.snapshot()['observations']), 3)
        self.assertEqual(len({r['payload_id'] for r in memory.snapshot()['observations']}), 1)

    def test_same_source_and_sequence_in_other_region_does_not_share_flag(self):
        a, b = ('conversation:a', 'copy', 1), ('conversation:b', 'copy', 1)
        packet = dict(candidates_with_provenance=[dict(payload_id='same-root', occurrences=[
            dict(origin=a, explicit_reply_to_selected_target=True),
            dict(origin=b, explicit_reply_to_selected_target=False)])])
        self.assertEqual(relation_flags(packet), {a: True, b: False})

    def test_fixture_has_five_user_copies_and_separate_unlinked_episode(self):
        rows, query, values, targets, links, late = fixtures(20261203)
        copies = [r for r in rows if r['text'] == values[0] and r['source_kind'] == 'user_turn']
        self.assertEqual(len(copies), 5)
        self.assertEqual(len(targets), 4)
        self.assertTrue(all(next(r for r in rows if (r['hierarchy_id'], r['source_id'], r['sequence']) == t)['text']
                            == query for t in targets))
        self.assertFalse(any((s, q, seq) == targets[2] for s, _, _, q, seq in links + [late]))
        self.assertEqual(fixtures(20261203), fixtures(20261203))
        self.assertNotEqual(values, fixtures(20261204)[2])

    @unittest.skipUnless(os.environ.get('MEMORIA_NATIVE_LIBRARY'), 'requires native BDR library')
    def test_native_relation_is_local_to_occurrence_and_survives_cold_reopen(self):
        for seed in (20261203, 20261204):
            with self.subTest(seed=seed):
                result = probe(Path(os.environ['MEMORIA_NATIVE_LIBRARY']), seed)
                self.assertEqual(result['integrity_passed'], 64)
                self.assertEqual(result['integrity_total'], 64)
                self.assertEqual(len(result['shared_payload_origins']), 5)
                self.assertEqual(result['unsafe_root_only_false_annotations'], 25)
                self.assertIsNone(result['answer'])
                self.assertFalse(result['qualified'])
                initial, linked, late = result['stages']
                # Same payload, yet flags differ by full address and selected episode.
                for case in initial['cases']:
                    self.assertFalse(any(relation_flags(case['joined']).values()))
                for case in linked['cases'] + late['cases']:
                    self.assertEqual({a for a, value in relation_flags(case['joined']).items() if value},
                                     set(case['expected_linked_origins']))
                self.assertEqual(linked['cases'][2]['joined'], late['cases'][2]['joined'])
                self.assertEqual(linked['cases'][3]['joined'], late['cases'][3]['joined'])


if __name__ == '__main__':
    unittest.main()
