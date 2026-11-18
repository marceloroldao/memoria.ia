import copy
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_contextual_relation_probe import contextual_relations, fixture, probe
from trajectory_inferred_relation_probe import score


def row(source, sequence, text, kind='user_turn', region='local'):
    return dict(hierarchy_id=region, source_id=source, sequence=sequence, text=text, source_kind=kind)


class ContextualRelationTests(unittest.TestCase):
    def test_one_observed_root_proposes_without_qualifying_or_selecting_target(self):
        rows = [row('q', 1, 'abc'), row('a', 2, 'def')]
        result = contextual_relations(rows, 'local', 'abc')
        for route in result['routes'].values():
            self.assertEqual(route['reason'], 'UNIQUE_CONTEXTUAL_ROOT')
            self.assertIsNotNone(route['proposal_payload_id'])
            self.assertIsNone(route['answer'])
            self.assertFalse(route['qualified'])
            self.assertIsNone(route['selected_target'])
            self.assertFalse(route['selection_used'])
            relation = route['episodes'][0]['inferred_relations'][0]
            self.assertEqual(relation['origin'], ('local', 'a', 2))
            self.assertFalse(relation['observed_reply_to'])

    def test_reference_interpretation_cannot_change_view_and_can_make_proposal_false(self):
        rows = [row('q', 1, 'abc'), row('a', 2, 'def')]
        before = copy.deepcopy(rows)
        view = contextual_relations(rows, 'local', 'abc')
        self.assertEqual(rows, before)
        positive = score(view, [(('local', 'q', 1), ('local', 'a', 2))], rows)
        negative = score(view, [], rows)
        self.assertTrue(all(s['exact_relation_set'] for s in positive.values()))
        self.assertTrue(all(s['false_positive'] == 1 for s in negative.values()))
        rows[1].update(reply_to=dict(source_id='arbitrary', sequence=999), hidden_role='unrelated')
        self.assertEqual(contextual_relations(rows, 'local', 'abc'), view)

    def test_competing_roots_remain_in_base_even_when_filter_abstains(self):
        rows = [row('q', 1, 'abc'), row('a', 2, 'def'), row('b', 3, 'ghi')]
        result = contextual_relations(rows, 'local', 'abc')
        base = result['base']['routes']['structural_successors']['episodes'][0]['inferred_relations']
        self.assertEqual({r['origin'][1] for r in base}, {'a'})
        for name, route in result['routes'].items():
            self.assertIsNone(route['proposal_payload_id'])
            self.assertEqual(result['audits'][name]['removed_inferred_relations'], base)
            temporal = result['audits'][name]['contextual_diagnostic']['generation']['temporal_evidence']
            self.assertEqual({tuple(r['symbols']) for r in temporal}, {tuple(map(ord, text)) for text in ('def', 'ghi')})

    def test_learned_fragment_is_retained_without_fabricating_complete_root(self):
        rows, region, query, _ = fixture(20261217, 'fragment_only')
        result = contextual_relations(rows, region, query)
        for name, audit in result['audits'].items():
            self.assertIsNotNone(audit['contextual_diagnostic']['hypothesis'])
            self.assertIsNone(audit['matched_observed_root'])
            self.assertFalse(audit['learned_fragment_promoted_to_root'])
            self.assertEqual(result['routes'][name]['reason'], 'NON_ROOT_CONTEXTUAL_HYPOTHESIS')

    def test_multiple_occurrences_of_same_query_cannot_choose_intended_episode(self):
        rows = [row('q', 1, 'abc'), row('a', 2, 'def'),
                row('barrier', 3, 'irrelevant', 'assistant_generated'), row('q2', 4, 'abc'), row('a2', 5, 'def')]
        result = contextual_relations(rows, 'local', 'abc')
        for route in result['routes'].values():
            self.assertEqual(len(route['episodes']), 2)
            self.assertEqual(route['reason'], 'AMBIGUOUS_TARGETS')
            self.assertIsNone(route['proposal_payload_id'])

    def test_generated_and_foreign_rows_cannot_supply_local_successors(self):
        rows = [row('q', 1, 'abc'), row('barrier', 2, 'def', 'assistant_generated'),
                row('a', 3, 'def'), row('foreign', 1, 'def', region='foreign')]
        result = contextual_relations(rows, 'local', 'abc')
        for route in result['routes'].values():
            self.assertEqual(route['episodes'][0]['inferred_relations'], [])
            self.assertIsNone(route['proposal_payload_id'])

    def test_invalid_addresses_are_rejected_before_contextual_read(self):
        source = row('q', 1, 'abc')
        for rows in ([source, copy.deepcopy(source)], [row('a', 2, 'def'), source],
                     [row('x', 1, 'abc', 'arbitrary')]):
            with self.assertRaises(ValueError):
                contextual_relations(rows, 'local', 'abc')

    @unittest.skipUnless(os.environ.get('MEMORIA_NATIVE_LIBRARY'), 'requires native BDR library')
    def test_native_contextual_filters_keep_false_links_misses_and_fragment_limit(self):
        for seed in (20261217, 20261218):
            result = probe(Path(os.environ['MEMORIA_NATIVE_LIBRARY']), seed)
            self.assertEqual(result['integrity_passed'], result['integrity_total'])
            self.assertEqual(len(result['cases']), 16)
            self.assertTrue(all(s['false_positive'] > 0 and s['false_negative'] > 0 for s in result['route_totals'].values()))
            self.assertTrue(all(matches == 1 for pair in result['hidden_relation_twins'] for matches in pair['route_matches'].values()))
            self.assertEqual(result['relation_quality_status'], 'FAIL_FALSE_OR_MISSING_RELATIONS')
            self.assertEqual(result['semantic_quality_status'], 'FAIL_HIDDEN_RELATION_TWINS')
            self.assertEqual(result['factual_quality_status'], 'NOT_EVALUATED')


if __name__ == '__main__':
    unittest.main()
