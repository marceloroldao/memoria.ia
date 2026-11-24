from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_analogy_two_slot_probe import checked, evaluate, probe
from trajectory_analogy_unmarked_probe import fixture
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


class TwoSlotTests(unittest.TestCase):
    def test_second_copied_slot_selects_the_matching_observed_root(self):
        report = evaluate(20261030, 'ordered')
        self.assertTrue(all(c['quality_pass'] for c in report['cases']))
        first, _, second = report['cases'][:3]
        self.assertNotEqual(first['expected'], second['expected'])
        for case in (first, second):
            self.assertEqual(case['result']['hypothesis'], case['expected'][0])
            self.assertFalse(case['result']['prior_value']['candidates'])
            self.assertTrue(case['result']['two_slot_frames'])

    def test_target_order_is_learned_from_examples(self):
        report = evaluate(20261030, 'reversed_order')
        self.assertTrue(all(c['quality_pass'] for c in report['cases']))
        self.assertEqual(report['cases'][0]['result']['two_slot_frames'][0]['target_order'], (1, 0))

    def test_conflict_remains_local_to_the_matching_second_slot(self):
        report = evaluate(20261030, 'conflict')
        for case in report['cases'][:2]:
            self.assertEqual({c['output'] for c in case['result']['candidates']}, set(case['expected']))
            self.assertIsNone(case['result']['hypothesis'])
        second = report['cases'][2]
        self.assertEqual(second['result']['hypothesis'], second['expected'][0])
        self.assertFalse(report['cases'][7]['result']['candidates'])

    def test_ambiguous_separator_keeps_all_splits_and_unanswered_positive_is_failure(self):
        report = evaluate(20261030, 'ambiguous_separator')
        for case in report['cases'][:3]:
            self.assertFalse(case['quality_pass'])
            self.assertFalse(case['false_unique'])
            self.assertFalse(case['result']['candidates'])
            alignment = case['result']['query_alignments'][0]
            self.assertEqual(len(alignment['slot_choices']), 2)
            self.assertFalse(alignment['authorized'])

    def test_renaming_and_second_seed_keep_decisions_and_all_negatives(self):
        for stage in ('ordered', 'reversed_order', 'conflict', 'ambiguous_separator'):
            a, b = evaluate(20261030, stage), evaluate(20261030, stage, True)
            for x, y in zip(a['cases'], b['cases']):
                self.assertEqual(x['quality_pass'], y['quality_pass'])
                self.assertEqual({tuple(1000000-s for s in c['output']) for c in x['result']['candidates']},
                                 {c['output'] for c in y['result']['candidates']})
            self.assertTrue(all(c['quality_pass'] for c in a['cases'][3:]))
        report = probe(20261031)
        self.assertEqual(report['counts']['passed'], 66)
        self.assertEqual(report['counts']['false_unique'], 0)

    def test_old_unmarked_field_counterexamples_remain_unresolved(self):
        for family in ('relation_two_no_anchor', 'relation_three_no_anchor'):
            pairs, fact, queries = fixture(20261028, family)
            memory = TrajectoryGenerationExperiment()
            for i, (source, target) in enumerate(pairs):
                memory.observe(source, observation_id=f'{i}:s', stream_id=f'train:{i}')
                memory.observe(target, observation_id=f'{i}:t', stream_id=f'train:{i}')
            memory.observe(fact, observation_id='fact', stream_id='fact')
            result = checked(memory, queries[0][1])
            self.assertFalse(result['two_slot_frames'])
            self.assertEqual(result['candidates'], result['prior_value']['candidates'])
            self.assertEqual(result['hypothesis'], fact)
