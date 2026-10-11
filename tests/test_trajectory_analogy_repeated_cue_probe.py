from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_analogy_repeated_cue_probe import evaluate, probe


class RepeatedCueTests(unittest.TestCase):
    def test_repeated_second_cue_learns_specific_route_then_preserves_broad_rival(self):
        stages = evaluate(20261103, 1)['stages']
        self.assertTrue(all(c['quality_pass'] for s in stages for c in s['cases']))
        self.assertEqual(stages[0]['cases'][0]['result']['reason'], 'PRIOR_SELECTOR_HYPOTHESIS_ONLY')
        self.assertEqual(stages[2]['cases'][0]['result']['reason'], 'COMPETING_ALIGNMENT_ROOTS')
        first = stages[0]['cases'][0]['result']['candidates'][0]['output']
        later = stages[2]['cases'][0]['result']
        self.assertIn(first, {c['output'] for c in later['candidates']})
        self.assertIsNone(later['hypothesis'])

    def test_repeated_first_cue_keeps_coverage_failure_and_false_unique_exposed(self):
        stages = evaluate(20261103, 0)['stages']
        self.assertFalse(stages[0]['cases'][0]['quality_pass'])
        self.assertFalse(stages[0]['cases'][0]['result']['candidates'])
        case = stages[2]['cases'][0]
        self.assertEqual(len(case['expected']), 2)
        self.assertEqual(len(case['result']['candidates']), 1)
        self.assertEqual(case['result']['reason'], 'UNIQUE_ROOT_WITH_COMPLETE_ALIGNMENT_SUPPORT')
        self.assertTrue(case['false_unique'])
        self.assertFalse(case['quality_pass'])

    def test_repeated_payloads_add_addresses_without_new_roots_or_resolving_conflict(self):
        for fixed in (0, 1):
            stages = evaluate(20261103, fixed)['stages']
            for before, after in ((stages[0], stages[1]), (stages[2], stages[3])):
                self.assertEqual(before['unique_root_count'], after['unique_root_count'])
                self.assertEqual(before['observation_count']+2, after['observation_count'])
                for a, b in zip(before['cases'], after['cases']):
                    self.assertEqual(a['result']['hypothesis'], b['result']['hypothesis'])
                    self.assertEqual({c['output'] for c in a['result']['candidates']},
                                     {c['output'] for c in b['result']['candidates']})

    def test_stage_provenance_does_not_include_future_observation_addresses(self):
        stages = evaluate(20261103, 1)['stages']
        for s in stages:
            self.assertEqual(sum(len(r['observation_addresses']) for r in s['root_provenance']),
                             s['observation_count'])
        addresses = {a for r in stages[0]['root_provenance'] for a in r['observation_addresses']}
        self.assertFalse(any(a.startswith(('broad:', 'repeat:')) for a in addresses))

    def test_bijection_preserves_output_roles_and_failures(self):
        for fixed in (0, 1):
            a, b = evaluate(20261103, fixed), evaluate(20261103, fixed, True)
            for x, y in zip(a['stages'], b['stages']):
                for c, d in zip(x['cases'], y['cases']):
                    self.assertEqual(c['quality_pass'], d['quality_pass'])
                    self.assertEqual(c['false_unique'], d['false_unique'])
                    self.assertEqual(c['result']['reason'], d['result']['reason'])
                    self.assertEqual({tuple(1000000-v for v in r['output']) for r in c['result']['candidates']},
                                     {r['output'] for r in d['result']['candidates']})

    def test_reserved_seed_keeps_quality_failures_and_absence_contract(self):
        report = probe(20261104)
        self.assertEqual(report['quality_status'], 'FAIL')
        self.assertEqual(report['counts'], dict(cases=48, passed=32, answer_cases=16,
            correct_answers=8, conflict_cases=16, conflicts_preserved=8,
            absence_cases=16, absence_empty=16, false_unique=8))
