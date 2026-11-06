from pathlib import Path
import os
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_region_reply_probe import fixtures, probe, regional_groups


class RegionReplyTests(unittest.TestCase):
    def test_region_filter_preserves_all_local_sources_without_mutation(self):
        packet = {'groups': [dict(trail_address='root', representative_text='x',
                                 sources=[{'hierarchy_id': 'a', 'sequence': 1},
                                          {'hierarchy_id': 'b', 'sequence': 2},
                                          {'hierarchy_id': 'a', 'sequence': 3}])]}
        self.assertEqual([s['sequence'] for s in regional_groups(packet, 'a')[0]['sources']],
                         [1, 3])
        self.assertEqual(len(packet['groups'][0]['sources']), 3)
        self.assertEqual(regional_groups(packet, 'missing'), [])

    def test_fixture_separates_identical_text_and_source_id_by_complete_address(self):
        scopes, values, rows, links, _ = fixtures(20261129)
        questions = [r for r in rows if r['text'] == values[0]]
        self.assertEqual(len(questions), 4)
        self.assertEqual({r['source_id'] for r in questions}, {'q'})
        self.assertEqual(len({(r['hierarchy_id'], r['source_id'], r['sequence'])
                              for r in questions}), 4)
        self.assertFalse(any(link[0] == scopes[2] for link in links))
        self.assertEqual(fixtures(20261129)[:4], fixtures(20261129)[:4])
        self.assertNotEqual(scopes, fixtures(20261130)[0])

    @unittest.skipUnless(os.environ.get('MEMORIA_NATIVE_LIBRARY'),
                         'requires built native BDR library')
    def test_native_address_scopes_recurrence_conflict_and_cold_parity(self):
        library = Path(os.environ['MEMORIA_NATIVE_LIBRARY'])
        for seed in (20261129, 20261130):
            with self.subTest(seed=seed):
                result = probe(library, seed)
                self.assertEqual(result['integrity_passed'], result['integrity_total'])
                self.assertEqual(result['integrity_total'], 28)
                self.assertIsNone(result['answer'])
                self.assertFalse(result['qualified'])
                self.assertEqual(result['factual_quality_status'], 'NOT_EVALUATED')


if __name__ == '__main__':
    unittest.main()
