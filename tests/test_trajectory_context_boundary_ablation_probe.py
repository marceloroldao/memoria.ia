from functools import lru_cache
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_context_boundary_ablation_probe import MODES, fixture, probe


@lru_cache(maxsize=1)
def report():
    return probe(20261122)


class ContextBoundaryAblationTests(unittest.TestCase):
    def test_only_source_boundary_changes_across_modes(self):
        for renamed in (False, True):
            variants = [fixture(20261122, mode, renamed) for mode in MODES]
            destination_views = [
                (
                    tuple(target for _, target in f['training_pairs']),
                    tuple(target for _, target in f['crossed_pairs']),
                    f['facts'],
                    f['rival'],
                )
                for f in variants
            ]
            self.assertEqual(len({repr(view) for view in destination_views}), 1)
            self.assertEqual(len({repr(f['contexts']) for f in variants}), 1)
            self.assertEqual(len({repr(f['bodies']) for f in variants}), 1)
            self.assertNotEqual(variants[0]['delimiter'], variants[1]['delimiter'])
            self.assertNotEqual(variants[0]['delimiter'], variants[2]['delimiter'])

    def test_explicit_boundary_preserves_observed_context_contract(self):
        r = report()
        explicit = r['by_mode']['explicit']
        explicit_cross = r['cross_control_by_mode']['explicit']
        self.assertEqual(explicit['passed'], explicit['cases'])
        self.assertEqual(explicit_cross['passed'], explicit_cross['cases'])
        self.assertEqual(r['semantic_quality_status'], 'UNQUALIFIED')

    def test_every_candidate_is_an_observed_root_and_never_authorized(self):
        for ev in report()['evaluations']:
            for stage in ev['stages']:
                roots = {row['payload_id'] for row in stage['provenance']}
                for case in stage['cases']:
                    packet = case['packet']
                    self.assertTrue({c['payload_id'] for c in packet['candidates']} <= roots)
                    self.assertIsNone(packet['answer'])
                    self.assertFalse(packet['qualified'])
                    self.assertFalse(packet['observed_continuations'])

    def test_repetition_does_not_create_new_payloads_or_erase_candidates(self):
        for ev in report()['evaluations']:
            crossed, repeated = ev['stages'][1:3]
            self.assertEqual(crossed['unique_payloads'], repeated['unique_payloads'])
            for before, after in zip(crossed['cases'], repeated['cases']):
                self.assertEqual(
                    {c['output'] for c in before['packet']['candidates']},
                    {c['output'] for c in after['packet']['candidates']},
                )
                self.assertEqual(
                    before['packet']['prior_structural_hypothesis'],
                    after['packet']['prior_structural_hypothesis'],
                )

    def test_rival_preserves_conflict_without_unique_authorization(self):
        for ev in report()['evaluations']:
            last = ev['stages'][-1]['cases'][0]
            outputs = {c['output'] for c in last['packet']['candidates']}
            self.assertTrue(set(last['expected']) <= outputs)
            self.assertIsNone(last['packet']['prior_structural_hypothesis'])

    def test_bijective_renaming_preserves_quality_per_mode(self):
        r = report()
        for mode in MODES:
            left, right = [ev for ev in r['evaluations'] if ev['mode'] == mode]
            for a_stage, b_stage in zip(left['stages'], right['stages']):
                for a, b in zip(a_stage['cases'], b_stage['cases']):
                    self.assertEqual(a['quality_pass'], b['quality_pass'])
                    self.assertEqual(
                        {tuple(1000000 - z for z in c['output']) for c in a['packet']['candidates']},
                        {c['output'] for c in b['packet']['candidates']},
                    )


if __name__ == '__main__':
    unittest.main()
