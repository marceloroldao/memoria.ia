from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_analogy_value_probe import checked, constant_controls, evaluate, learn_values
from trajectory_analogy_stress_probe import FAMILIES
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


class RepeatedValueTests(unittest.TestCase):
    def test_two_equal_values_recover_both_positive_forms(self):
        for case in evaluate(20261026, 'two_equal_values')['cases'][:2]:
            self.assertEqual(case['result']['hypothesis'], case['expected'][0])
            self.assertIsNone(case['result']['prior_copy']['hypothesis'])
            self.assertTrue(case['quality_pass'])

    def test_constant_training_does_not_authorize_an_unseen_different_tail(self):
        for case in evaluate(20261026, 'constant_value')['cases'][:2]:
            self.assertTrue(case['result']['value_frames'][0]['fixed_tail'])
            self.assertFalse(case['result']['candidates'])
            self.assertFalse(case['quality_pass'])
            self.assertFalse(case['false_unique'])

    def test_fixed_tail_controls_recover_exact_root_reject_change_and_keep_conflict(self):
        for renamed in (False, True):
            cases = constant_controls(20261026, renamed)
            self.assertTrue(all(c['quality_pass'] for c in cases))
            self.assertEqual(len(cases[0]['result']['candidates']), 1)
            self.assertFalse(cases[1]['result']['candidates'])
            self.assertEqual(len(cases[2]['result']['candidates']), 2)
            self.assertIsNone(cases[2]['result']['hypothesis'])

    def test_repeated_payloads_cannot_supply_three_distinct_source_variables(self):
        memory = TrajectoryGenerationExperiment()
        for repetition in range(4):
            for i in range(2):
                stream = f'{repetition}:{i}'
                memory.observe((1, 10+i, 2), observation_id=stream+':s', stream_id=stream)
                memory.observe((3, 10+i, 4, 77, 5), observation_id=stream+':t', stream_id=stream)
        self.assertFalse(learn_values(memory))

    def test_fixed_tail_supports_repeated_copies_and_refuses_corruption(self):
        memory = TrajectoryGenerationExperiment()
        for i in range(3):
            memory.observe((1, 10+i, 2), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe((3, 10+i, 4, 10+i, 6, 77, 5), observation_id=f'{i}:t', stream_id=str(i))
        fact = (3, 13, 4, 13, 6, 77, 5)
        memory.observe(fact, observation_id='fact', stream_id='fact')
        memory.observe((3, 13, 4, 14, 6, 77, 5), observation_id='wrong', stream_id='wrong')
        self.assertEqual(checked(memory, (1, 13, 2))['hypothesis'], fact)
        self.assertFalse(checked(memory, (1, 13, 2, 1, 14, 2))['candidates'])

    def test_two_value_mixed_relation_keeps_internal_anchor_veto(self):
        memory = TrajectoryGenerationExperiment()
        for i in range(3):
            memory.observe((1, 10+i, 2), observation_id=f'{i}:s', stream_id=str(i))
            tag, value = (40, 77) if i<2 else (41, 78)
            memory.observe((3, 10+i, 6, tag, 7, value, 5),
                           observation_id=f'{i}:t', stream_id=str(i))
        memory.observe((3, 13, 6, 42, 7, 79, 5), observation_id='fact', stream_id='fact')
        result = checked(memory, (1, 13, 2))
        self.assertTrue(result['value_frames'][0]['internal_anchors'])
        self.assertFalse(result['candidates'])

    def test_other_families_keep_prior_candidates_and_renaming_is_equivariant(self):
        for family in FAMILIES:
            if family=='two_equal_values':
                continue
            for case in evaluate(20261026, family)['cases']:
                self.assertEqual(case['result']['candidates'], case['result']['prior_copy']['candidates'])
                self.assertEqual(case['result']['hypothesis'], case['result']['prior_copy']['hypothesis'])
        a, b = evaluate(20261026, 'two_equal_values'), evaluate(20261026, 'two_equal_values', True)
        for x, y in zip(a['cases'], b['cases']):
            self.assertEqual(x['quality_pass'], y['quality_pass'])
            self.assertEqual({tuple(1000000-s for s in c['output']) for c in x['result']['candidates']},
                             {c['output'] for c in y['result']['candidates']})
