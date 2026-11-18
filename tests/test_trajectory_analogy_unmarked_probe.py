from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_analogy_unmarked_probe import evaluate, fixture, probe


class UnmarkedFieldTests(unittest.TestCase):
    def test_two_value_extension_exposes_new_unsupported_selections(self):
        report = evaluate(20261028, 'relation_two_no_anchor')
        for case in report['cases'][:2]:
            self.assertTrue(case['false_unique'])
            self.assertFalse(case['prior_false_unique'])
            self.assertFalse(case['quality_pass'])
            self.assertEqual(case['result']['hypothesis'], report['isolated_fact'])
            self.assertTrue(case['result']['value_frames'])
            self.assertFalse(case['result']['value_frames'][0]['internal_anchors'])

    def test_three_value_failure_already_exists_in_prior_selector(self):
        for case in evaluate(20261028, 'relation_three_no_anchor')['cases'][:2]:
            self.assertTrue(case['false_unique'])
            self.assertTrue(case['prior_false_unique'])
            self.assertEqual(case['result']['hypothesis'], case['result']['prior_copy']['hypothesis'])

    def test_identical_observations_support_incompatible_scoring_contracts(self):
        free = evaluate(20261028, 'whole_value_two')
        relation = evaluate(20261028, 'relation_two_no_anchor')
        self.assertEqual(free['training_pairs'], relation['training_pairs'])
        self.assertEqual(free['isolated_fact'], relation['isolated_fact'])
        for a, b in zip(free['cases'], relation['cases']):
            self.assertEqual(a['query'], b['query'])
            self.assertEqual(a['result'], b['result'])
        self.assertTrue(free['cases'][0]['quality_pass'])
        self.assertFalse(relation['cases'][0]['quality_pass'])
        self.assertNotEqual(free['cases'][0]['expected'], relation['cases'][0]['expected'])

    def test_internal_anchor_and_exact_constant_controls_still_pass(self):
        for family in ('relation_two_with_anchor', 'fixed_tail_matching', 'fixed_tail_changed'):
            self.assertTrue(all(c['quality_pass'] for c in evaluate(20261028, family)['cases']))

    def test_bijective_renaming_preserves_success_and_failure(self):
        for family in ('whole_value_two', 'relation_two_no_anchor', 'relation_three_no_anchor'):
            a, b = evaluate(20261028, family), evaluate(20261028, family, True)
            for x, y in zip(a['cases'], b['cases']):
                self.assertEqual(x['quality_pass'], y['quality_pass'])
                self.assertEqual(x['false_unique'], y['false_unique'])
                transformed = None if x['result']['hypothesis'] is None else tuple(
                    1000000-s for s in x['result']['hypothesis'])
                self.assertEqual(transformed, y['result']['hypothesis'])

    def test_second_seed_retains_failures_and_other_negatives_stay_empty(self):
        report = probe(20261029)
        self.assertEqual(report['quality_status'], 'FAIL')
        self.assertEqual(report['counts']['false_unique'], 8)
        self.assertEqual(report['counts']['prior_false_unique'], 4)
        for family in report['families']:
            for case in family['cases'][2:]:
                self.assertFalse(case['result']['candidates'])
                self.assertTrue(case['quality_pass'])
