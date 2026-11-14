from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_analogy_boundary_probe import checked, evaluate, extract
from trajectory_analogy_stress_probe import FAMILIES
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


class BoundaryShadowTests(unittest.TestCase):
    def test_missing_suffix_recovers_both_positive_forms(self):
        report = evaluate(20261022, 'no_source_suffix')
        self.assertTrue(all(c['quality_pass'] for c in report['cases']))
        for case in report['cases'][:2]:
            self.assertEqual(case['result']['hypothesis'], case['expected'][0])
            self.assertIsNone(case['prior_shadow']['hypothesis'])

    def test_missing_prefix_requires_exact_start_and_keeps_failed_positive_visible(self):
        cases = evaluate(20261022, 'no_source_prefix')['cases']
        self.assertTrue(cases[0]['quality_pass'])
        self.assertFalse(cases[1]['quality_pass'])
        self.assertIsNone(cases[1]['result']['hypothesis'])
        self.assertTrue(cases[3]['quality_pass'])
        self.assertFalse(cases[3]['result']['candidates'])

    def test_earlier_frames_and_decisions_are_unchanged_for_two_boundaries(self):
        for family in FAMILIES:
            if family in ('no_source_prefix', 'no_source_suffix'):
                continue
            for case in evaluate(20261022, family)['cases']:
                self.assertEqual(case['result']['candidates'], case['prior_shadow']['candidates'])
                self.assertEqual(case['result']['hypothesis'], case['prior_shadow']['hypothesis'])

    def test_conflict_is_preserved_with_missing_suffix(self):
        memory = TrajectoryGenerationExperiment()
        for i in range(3):
            memory.observe((1, 10+i), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe((3, 10+i, 4, 20+i, 5), observation_id=f'{i}:t', stream_id=str(i))
        facts = ((3, 13, 4, 23, 5), (3, 13, 4, 99, 5))
        for i, fact in enumerate(facts):
            memory.observe(fact, observation_id=f'fact:{i}', stream_id=f'fact:{i}')
        result = checked(memory, (1, 13))
        self.assertEqual({c['output'] for c in result['candidates']}, set(facts))
        self.assertIsNone(result['hypothesis'])
        self.assertFalse(checked(memory, (1, 13, 1, 14))['candidates'])

    def test_no_source_boundary_is_not_authorized_and_empty_boundary_extraction_is_exact(self):
        self.assertEqual(extract((1, 2), (), (2,)), (1,))
        self.assertEqual(extract((1, 2), (1,), ()), (2,))
        self.assertIsNone(extract((1,), (1,), ()))
        memory = TrajectoryGenerationExperiment()
        for i in range(3):
            memory.observe((10+i,), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe((3, 10+i, 4, 20+i, 5), observation_id=f'{i}:t', stream_id=str(i))
        memory.observe((3, 13, 4, 23, 5), observation_id='fact', stream_id='fact')
        self.assertFalse(checked(memory, (13,))['candidates'])

    def test_renaming_preserves_outputs_and_mixed_relation_veto(self):
        for family in ('no_source_prefix', 'no_source_suffix', 'varying_tag'):
            a, b = evaluate(20261022, family), evaluate(20261022, family, True)
            for x, y in zip(a['cases'], b['cases']):
                self.assertEqual(x['quality_pass'], y['quality_pass'])
                self.assertEqual({tuple(1000000-s for s in c['output'])
                                  for c in x['result']['candidates']},
                                 {c['output'] for c in y['result']['candidates']})
