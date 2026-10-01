from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_analogy_copy_probe import checked, evaluate, learn_copies
from trajectory_analogy_stress_probe import FAMILIES
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def trained(mixed=False):
    memory = TrajectoryGenerationExperiment()
    for i in range(3):
        memory.observe((1, 10+i, 2), observation_id=f'{i}:s', stream_id=str(i))
        tail = (6, 40+i, 7, 20+i, 5) if mixed else (6, 20+i, 5)
        memory.observe((3, 10+i, 4, 10+i)+tail,
                       observation_id=f'{i}:t', stream_id=str(i))
    return memory


class RepeatedCopyTests(unittest.TestCase):
    def test_both_positive_forms_recover_all_copies(self):
        for case in evaluate(20261024, 'copied_twice')['cases'][:2]:
            self.assertEqual(case['result']['hypothesis'], case['expected'][0])
            self.assertIsNone(case['result']['prior_boundary']['hypothesis'])
            self.assertEqual(len(case['result']['copy_frames'][0]['target_parts']), 2)
            self.assertTrue(case['quality_pass'])

    def test_one_corrupt_copy_and_unexpected_extra_copy_are_rejected(self):
        memory = trained()
        for i, fact in enumerate(((3, 13, 4, 14, 6, 23, 5),
                                  (3, 13, 4, 13, 6, 23, 13, 5))):
            memory.observe(fact, observation_id=f'fact:{i}', stream_id=f'fact:{i}')
        self.assertFalse(checked(memory, (1, 13, 2))['candidates'])

    def test_two_whole_destinations_conflict_and_two_query_cues_abstain(self):
        memory = trained()
        facts = ((3, 13, 4, 13, 6, 23, 5), (3, 13, 4, 13, 6, 99, 5))
        for i, fact in enumerate(facts):
            memory.observe(fact, observation_id=f'fact:{i}', stream_id=f'fact:{i}')
        result = checked(memory, (1, 13, 2))
        self.assertEqual({c['output'] for c in result['candidates']}, set(facts))
        self.assertIsNone(result['hypothesis'])
        self.assertFalse(checked(memory, (1, 13, 2, 1, 14, 2))['candidates'])

    def test_single_and_repeated_copy_routes_compete_without_priority(self):
        memory = trained()
        for i in range(3):
            memory.observe((1, 10+i, 2), observation_id=f'old:{i}:s', stream_id=f'old:{i}')
            memory.observe((9, 10+i, 8, 20+i, 5),
                           observation_id=f'old:{i}:t', stream_id=f'old:{i}')
        facts = ((3, 13, 4, 13, 6, 23, 5), (9, 13, 8, 23, 5))
        for i, fact in enumerate(facts):
            memory.observe(fact, observation_id=f'fact:{i}', stream_id=f'fact:{i}')
        result = checked(memory, (1, 13, 2))
        self.assertEqual({c['output'] for c in result['candidates']}, set(facts))
        self.assertEqual(len(result['prior_boundary']['candidates']), 1)
        self.assertIsNone(result['hypothesis'])

    def test_mixed_relation_inside_repeated_copy_tail_remains_vetoed(self):
        memory = trained(mixed=True)
        memory.observe((3, 13, 4, 13, 6, 43, 7, 23, 5), observation_id='fact', stream_id='fact')
        result = checked(memory, (1, 13, 2))
        self.assertTrue(result['copy_frames'][0]['internal_anchors'])
        self.assertFalse(result['candidates'])

    def test_inconsistent_or_overlapping_copies_cannot_train(self):
        memory = TrajectoryGenerationExperiment()
        for i in range(3):
            memory.observe((1, 10+i, 2), observation_id=f'{i}:s', stream_id=str(i))
            target = (3, 10+i, 4)+(10+i, 6)*(i+1)+(20+i, 5)
            memory.observe(target, observation_id=f'{i}:t', stream_id=str(i))
        self.assertFalse(learn_copies(memory))
        overlap = TrajectoryGenerationExperiment()
        for i in range(3):
            overlap.observe((1, 10+i, 10+i, 2), observation_id=f'{i}:s', stream_id=str(i))
            overlap.observe((3, 10+i, 10+i, 10+i, 6, 20+i, 5),
                            observation_id=f'{i}:t', stream_id=str(i))
        self.assertFalse(learn_copies(overlap))

    def test_other_families_keep_prior_decisions_and_renaming_is_equivariant(self):
        for family in FAMILIES:
            for case in evaluate(20261024, family)['cases']:
                if family != 'copied_twice':
                    self.assertEqual(case['result']['candidates'], case['result']['prior_boundary']['candidates'])
                    self.assertEqual(case['result']['hypothesis'], case['result']['prior_boundary']['hypothesis'])
        a, b = evaluate(20261024, 'copied_twice'), evaluate(20261024, 'copied_twice', True)
        for x, y in zip(a['cases'], b['cases']):
            self.assertEqual(x['quality_pass'], y['quality_pass'])
            self.assertEqual({tuple(1000000-s for s in c['output']) for c in x['result']['candidates']},
                             {c['output'] for c in y['result']['candidates']})
