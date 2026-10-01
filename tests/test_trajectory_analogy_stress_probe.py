from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_analogy_stress_probe import evaluate,fixture


class AnalogyStressTests(unittest.TestCase):
    def test_invariant_relation_recovers_only_the_matching_observed_root(self):
        for family in ('baseline','invariant_tag'):
            report=evaluate(20261016,family)
            self.assertEqual(report['quality_status'],'PASS')
            known=report['cases'][0]
            self.assertEqual(known['result']['hypothesis'],known['expected'][0])
            self.assertEqual(len(known['result']['candidates']),1)
            self.assertTrue(all(not c['result']['candidates'] for c in report['cases'][2:]))

    def test_mixed_relation_counterexample_is_scored_as_an_unsupported_unique_selection(self):
        report=evaluate(20261016,'varying_tag')
        for case in report['cases'][:2]:
            self.assertEqual(case['kind'],'absence')
            self.assertTrue(case['false_unique'])
            self.assertFalse(case['quality_pass'])
            self.assertIn(case['result']['hypothesis'],report['isolated_roots'])
            self.assertEqual(len(case['result']['candidates']),1)
        self.assertEqual(report['quality_status'],'FAIL')

    def test_unanswered_positive_cases_are_failures_without_becoming_false_selections(self):
        for family in ('constant_value','copied_twice','identifier_contains_prefix',
                       'shared_value_prefix','shared_value_suffix'):
            case=evaluate(20261016,family)['cases'][0]
            self.assertEqual(case['kind'],'answer')
            self.assertIsNone(case['result']['hypothesis'])
            self.assertFalse(case['correct_answer'])
            self.assertFalse(case['quality_pass'])
            self.assertFalse(case['false_unique'])

    def test_bijective_renaming_preserves_successes_and_the_mixed_relation_failure(self):
        for family in ('baseline','invariant_tag','varying_tag','identifier_contains_prefix'):
            original=evaluate(20261016,family)
            renamed=evaluate(20261016,family,True)
            for a,b in zip(original['cases'],renamed['cases']):
                self.assertEqual(a['quality_pass'],b['quality_pass'])
                self.assertEqual(a['false_unique'],b['false_unique'])
                expected=None if a['result']['hypothesis'] is None else tuple(
                    1000000-x for x in a['result']['hypothesis'])
                self.assertEqual(expected,b['result']['hypothesis'])

    def test_mixed_and_invariant_controls_differ_only_in_the_generated_relation_field(self):
        normal_pairs,normal_facts,normal_queries=fixture(20261016,'invariant_tag')
        mixed_pairs,mixed_facts,mixed_queries=fixture(20261016,'varying_tag')
        self.assertEqual([s for s,_ in normal_pairs],[s for s,_ in mixed_pairs])
        self.assertEqual([q for _,q,_,_ in normal_queries],[q for _,q,_,_ in mixed_queries])
        self.assertNotEqual([t for _,t in normal_pairs],[t for _,t in mixed_pairs])
        self.assertEqual(normal_facts[1],mixed_facts[1])
        self.assertNotEqual(normal_facts[0],mixed_facts[0])
