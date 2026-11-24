from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_analogy_evidence_probe import evaluate, probe


class EvidenceInterventionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = evaluate(20261020)
        cls.renamed = evaluate(20261020, True)

    def test_three_distinct_examples_unlock_observed_answer(self):
        stage = self.original['stages'][3]
        for case in stage['cases'][:2]:
            self.assertEqual(case['result']['hypothesis'], case['expected'][0])
            self.assertTrue(case['quality_pass'])
            self.assertTrue(stage['blocked_frames'])
            self.assertEqual(len(case['result']['candidates']), 1)

    def test_payload_repetition_preserves_root_count_and_cannot_unlock_answer(self):
        two, repeated = self.original['stages'][1:3]
        self.assertEqual(two['distinct_roots'], repeated['distinct_roots'])
        self.assertEqual(repeated['observations']-two['observations'], 6)
        for stage in self.original['stages']:
            self.assertEqual(sum(len(r['observation_addresses']) for r in stage['root_provenance']),
                             stage['observations'])
        self.assertTrue(any(len(r['observation_addresses']) == 4
                            for r in repeated['root_provenance']))
        for case in repeated['cases']:
            self.assertFalse(case['result']['candidates'])
            self.assertTrue(case['quality_pass'])

    def test_two_supported_relations_preserve_both_whole_roots(self):
        for case in self.original['stages'][4]['cases'][:2]:
            self.assertEqual({c['output'] for c in case['result']['candidates']},
                             set(case['expected']))
            self.assertIsNone(case['result']['hypothesis'])
            self.assertTrue(case['quality_pass'])

    def test_negatives_stay_empty_through_all_interventions(self):
        for stage in self.original['stages']:
            for case in stage['cases'][2:]:
                self.assertFalse(case['result']['candidates'])
                self.assertTrue(case['quality_pass'])

    def test_renaming_preserves_every_stage_and_second_seed_contracts(self):
        for a, b in zip(self.original['stages'], self.renamed['stages']):
            for x, y in zip(a['cases'], b['cases']):
                self.assertEqual(x['quality_pass'], y['quality_pass'])
                self.assertEqual({tuple(1000000-s for s in c['output'])
                                  for c in x['result']['candidates']},
                                 {c['output'] for c in y['result']['candidates']})
        self.assertEqual(probe(20261021)['quality_status'], 'PASS')
