from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_observed_variant_probe import run_fixture, score
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


FIXTURE = ((1, 2, 3, 4), (11, 2, 3, 14), (7, 8, 9), (17, 18, 19),
           (100, 101), (11, 2, 3, 24), (30, 31, 32))


class ObservedVariantScoringTests(unittest.TestCase):
    def test_wrong_fragment_cannot_pass_as_retained_answer_or_absence(self):
        result = TrajectoryGenerationExperiment().contextual_route_hypothesis((7, 8, 9))
        wrong = replace(result, hypothesis=(7, 8))
        self.assertFalse(score(wrong, ((7, 8, 9),), 'answer')['quality_pass'])
        self.assertTrue(score(wrong, (), 'absence')['false_unique'])
        self.assertFalse(score(wrong, (), 'absence')['quality_pass'])
        self.assertTrue(score(replace(result, hypothesis=(0, 7, 8, 9, 0)),
                              ((7, 8, 9),), 'answer')['correct_answer'])

    def test_conflict_requires_both_full_targets_and_abstention(self):
        memory = TrajectoryGenerationExperiment()
        for i, target in enumerate(((7, 8, 9), (17, 18, 19))):
            memory.observe((1, 2, 3), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe(target, observation_id=f'{i}:t', stream_id=str(i))
        result = memory.contextual_route_hypothesis((1, 2, 3))
        expected = ((7, 8, 9), (17, 18, 19))
        self.assertTrue(score(result, expected, 'conflict')['quality_pass'])
        self.assertFalse(score(replace(result, hypothesis=expected[0]), expected,
                               'conflict')['quality_pass'])
        missing = replace(result, generation=replace(result.generation,
                           candidates=tuple(c for c in result.generation.candidates
                                            if c.output != expected[1])))
        self.assertFalse(score(missing, expected, 'conflict')['quality_pass'])

    def test_fixture_keeps_source_only_unanswered_and_reuses_repeated_content(self):
        rows, records = run_fixture(*FIXTURE)
        for row in rows:
            if row['stage'] in ('unseen', 'source_only') and row['name'] in ('variant', 'new_prefix'):
                self.assertEqual(row['kind'], 'absence')
                self.assertTrue(row['quality_pass'])
        by_stage = {r['stage']: r for r in records}
        self.assertEqual(by_stage['paired']['unique_payloads'], by_stage['repeated']['unique_payloads'])
        self.assertEqual(len(by_stage['repeated']['observations']), 8)
        self.assertTrue(all(not row['receipt']['learned'] and row['receipt']['new_relations'] == 0
                            for row in by_stage['repeated']['observations'][4:]))

    def test_numeric_renaming_keeps_quality_and_hypothesis(self):
        rows, _ = run_fixture(*FIXTURE)
        renamed, _ = run_fixture(*(tuple(10000 - x for x in p) for p in FIXTURE))
        for a, b in zip(rows, renamed):
            self.assertEqual((a['stage'], a['name'], a['quality_pass'], a['false_unique']),
                             (b['stage'], b['name'], b['quality_pass'], b['false_unique']))
            hypothesis = a['result']['hypothesis']
            self.assertEqual(None if hypothesis is None else tuple(10000 - x for x in hypothesis),
                             b['result']['hypothesis'])


if __name__ == '__main__':
    unittest.main()
