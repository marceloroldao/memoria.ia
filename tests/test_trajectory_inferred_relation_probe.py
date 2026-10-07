import copy
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_inferred_relation_probe import inferred_relations, probe


def row(source, sequence, text, kind='user_turn', region='local'):
    return dict(hierarchy_id=region, source_id=source, sequence=sequence, text=text, source_kind=kind)


class InferredRelationTests(unittest.TestCase):
    def test_links_and_evaluator_metadata_are_masked_before_learning(self):
        rows = [row('q', 1, 'abc'), row('a', 2, 'def')]
        before = copy.deepcopy(rows)
        result = inferred_relations(rows, 'local', 'abc')
        self.assertEqual(rows, before)
        rows[1].update(reply_to=dict(source_id='different', sequence=100), hidden_expected='wrong',
                       previous_source_id='forged', next_sequence=-10)
        self.assertEqual(inferred_relations(rows, 'local', 'abc'), result)
        route = result['routes']['adjacent']
        self.assertIsNotNone(route['proposal_payload_id'])
        self.assertFalse(route['qualified'])
        self.assertIsNone(route['answer'])
        self.assertIsNone(route['selected_target'])
        self.assertFalse(route['selection_used'])
        self.assertFalse(route['episodes'][0]['inferred_relations'][0]['observed_reply_to'])

    def test_generated_copy_blocks_successor_and_is_not_a_target(self):
        rows = [row('q', 1, 'abc'), row('generated', 2, 'abc', 'assistant_generated'), row('a', 3, 'def')]
        result = inferred_relations(rows, 'local', 'abc')
        self.assertEqual(result['targets'], [('local', 'q', 1)])
        for route in result['routes'].values():
            self.assertEqual(route['episodes'][0]['inferred_relations'], [])
            self.assertIsNone(route['proposal_payload_id'])

    def test_same_payload_in_different_episodes_keeps_identity_and_abstains(self):
        rows = [row('q', 1, 'abc'), row('a', 2, 'def'), row('q2', 3, 'abc'), row('a2', 4, 'def')]
        result = inferred_relations(rows, 'local', 'abc')['routes']['adjacent']
        self.assertEqual(result['reason'], 'AMBIGUOUS_TARGETS')
        self.assertIsNone(result['proposal_payload_id'])
        first, second = [e['inferred_relations'][0] for e in result['episodes']]
        self.assertEqual(first['payload_id'], second['payload_id'])
        self.assertNotEqual(first['origin'], second['origin'])
        self.assertNotEqual(first['target'], second['target'])

    def test_foreign_rows_cannot_supply_local_successors(self):
        rows = [row('q', 1, 'abc'), row('a', 1, 'def', region='foreign')]
        result = inferred_relations(rows, 'local', 'abc')
        self.assertEqual(result['routes']['adjacent']['episodes'][0]['inferred_relations'], [])

    def test_unseen_raw_query_does_not_fabricate_an_episode(self):
        result = inferred_relations([row('q', 1, 'abc'), row('a', 2, 'def')], 'local', 'xyz')
        self.assertEqual(result['targets'], [])
        for route in result['routes'].values():
            self.assertEqual(route['reason'], 'NO_OBSERVED_TARGET')
            self.assertEqual(route['episodes'], [])

    def test_duplicate_out_of_order_and_unknown_source_kind_are_rejected(self):
        data = [row('q', 1, 'abc'), row('a', 2, 'def')]
        bad_rows = [data + [copy.deepcopy(data[0])], list(reversed(data)),
                    [row('x', 1, 'abc', 'generated-looking-user')]]
        for rows in bad_rows:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                inferred_relations(rows, 'local', 'abc')
        for region, query in [('', 'abc'), ('local', ''), (None, 'abc')]:
            with self.assertRaises(ValueError):
                inferred_relations(data, region, query)

    def test_temporal_order_changes_inferred_origin_without_changing_root_inventory(self):
        first = [row('q', 1, 'abc'), row('a', 2, 'def'), row('b', 3, 'ghi')]
        second = [row('q', 1, 'abc'), row('b', 2, 'ghi'), row('a', 3, 'def')]
        results = [inferred_relations(rows, 'local', 'abc')['routes']['adjacent'] for rows in (first, second)]
        self.assertNotEqual(results[0]['proposal_payload_id'], results[1]['proposal_payload_id'])
        self.assertEqual([r['episodes'][0]['inferred_relations'][0]['origin'][1] for r in results], ['a', 'b'])

    @unittest.skipUnless(os.environ.get('MEMORIA_NATIVE_LIBRARY'), 'requires native BDR library')
    def test_native_false_links_misses_link_masking_and_hidden_twins(self):
        for seed in (20261215, 20261216):
            result = probe(Path(os.environ['MEMORIA_NATIVE_LIBRARY']), seed)
            self.assertEqual(result['integrity_passed'], result['integrity_total'])
            self.assertEqual(len(result['cases']), 13)
            self.assertEqual(result['hidden_relation_twins']['route_matches']['adjacent'], 1)
            self.assertTrue(all(t['false_positive'] > 0 and t['false_negative'] > 0
                                for t in result['route_totals'].values()))
            self.assertEqual(result['relation_quality_status'], 'FAIL_FALSE_OR_MISSING_RELATIONS')
            self.assertEqual(result['semantic_quality_status'], 'FAIL_HIDDEN_RELATION_TWINS')
            self.assertEqual(result['factual_quality_status'], 'NOT_EVALUATED')


if __name__ == '__main__':
    unittest.main()
