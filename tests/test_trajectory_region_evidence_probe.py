from functools import lru_cache
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_boundary_length_probe import fixture
from trajectory_region_evidence_probe import checked, compact_report, probe, region_view
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


@lru_cache(maxsize=1)
def report():
    return probe(20261128)


def named(stage, name):
    return next(c for c in stage['cases'] if c['name'] == name)


class RegionEvidenceTests(unittest.TestCase):
    def test_scoped_roots_do_not_replace_global_competition(self):
        for ev in report()['evaluations']:
            stage = ev['stages'][0]
            outputs = lambda name: {c['output'] for c in named(stage, name)['result']['packet']['candidates']}
            self.assertEqual(outputs('global'), {ev['fixture']['fact'], ev['fixture']['rival']})
            self.assertEqual(outputs('left'), {ev['fixture']['fact']})
            self.assertEqual(outputs('right'), {ev['fixture']['rival']})
            self.assertTrue(all(c['quality_pass'] for c in stage['cases']))

    def test_scope_preserves_original_addresses_and_frame_witness_regions(self):
        for ev in report()['evaluations']:
            for stage in ev['stages']:
                original = {r['observation_id']: r for r in stage['provenance']}
                for c in stage['cases']:
                    view = c['result']
                    rows = view['selected_observations']
                    for row in rows:
                        self.assertEqual(row, original[row['observation_id']])
                        self.assertTrue(c['region'] is None or row['hierarchy_id'] == c['region'])
                    for frame in view['packet']['boundary_frames']:
                        for source, target, stream in frame['witnesses']:
                            self.assertTrue(any(r['payload_id'] == source and r['stream_id'] == stream for r in rows))
                            self.assertTrue(any(r['payload_id'] == target and r['stream_id'] == stream for r in rows))
                    self.assertIsNone(view['answer'])
                    self.assertFalse(view['qualified'])

    def test_foreign_repetition_does_not_vote_into_the_other_scope(self):
        for ev in report()['evaluations']:
            first, repeated = ev['stages'][:2]
            self.assertEqual(first['unique_payloads'], repeated['unique_payloads'])
            self.assertEqual(named(first, 'left')['result'], named(repeated, 'left')['result'])
            for name in ('global', 'right'):
                before = named(first, name)['result']['packet']
                after = named(repeated, name)['result']['packet']
                self.assertEqual({c['output'] for c in before['candidates']}, {c['output'] for c in after['candidates']})
                self.assertEqual(before['prior_structural_hypothesis'], after['prior_structural_hypothesis'])

    def test_same_region_late_rival_reopens_conflict_with_no_new_global_payload(self):
        for ev in report()['evaluations']:
            before, late = ev['stages'][1:]
            self.assertEqual(before['unique_payloads'], late['unique_payloads'])
            self.assertEqual(named(before, 'right')['result'], named(late, 'right')['result'])
            view = named(late, 'left')['result']
            self.assertEqual({c['output'] for c in view['packet']['candidates']}, {ev['fixture']['fact'], ev['fixture']['rival']})
            self.assertIsNone(view['packet']['prior_structural_hypothesis'])
            self.assertTrue(any(r['observation_id'] == 'left:late-rival' for r in view['selected_observations']))

    def test_unknown_scope_and_partial_regions_do_not_borrow_frames(self):
        for ev in report()['evaluations']:
            for stage in ev['stages']:
                for name in ('unknown_region', 'unknown_body', 'isolated_root_without_frames'):
                    self.assertFalse(named(stage, name)['result']['packet']['candidates'])
        data = fixture(20261128, True, True)
        memory = TrajectoryGenerationExperiment()
        for i, (source, target) in enumerate(data['training_pairs'][:3]):
            scope = 'region-a' if i < 2 else 'region-b'
            memory.observe(source, observation_id=f'{i}:source', hierarchy_id=scope, stream_id=str(i))
            memory.observe(target, observation_id=f'{i}:target', hierarchy_id=scope, stream_id=str(i))
        memory.observe(data['fact'], observation_id='fact', hierarchy_id='region-a', stream_id='fact')
        q = data['queries'][0][1]
        self.assertTrue(checked(memory, q)['packet']['candidates'])
        self.assertFalse(checked(memory, q, 'region-a')['packet']['candidates'])
        self.assertFalse(checked(memory, q, 'region-b')['packet']['candidates'])
        for invalid in ('', '  ', 1, []):
            with self.assertRaises(ValueError):
                region_view(memory, invalid)

    def test_symbol_and_metadata_bijection_preserve_outputs(self):
        a, b = report()['evaluations']
        for left, right in zip(a['stages'], b['stages']):
            for lc, rc in zip(left['cases'], right['cases']):
                self.assertEqual(lc['quality_pass'], rc['quality_pass'])
                self.assertEqual({tuple(1000000 - s for s in c['output']) for c in lc['result']['packet']['candidates']},
                                 {c['output'] for c in rc['result']['packet']['candidates']})

    def test_identical_region_observations_cannot_reveal_evaluator_only_roles(self):
        for ev in report()['evaluations']:
            twin = ev['hidden_role_twins']
            self.assertEqual(len(set(twin['snapshot_fingerprints'])), 1)
            self.assertEqual(len(set(twin['result_fingerprints'])), 1)
            self.assertNotEqual(twin['cases'][0]['expected'], twin['cases'][1]['expected'])
            self.assertEqual([c['quality_pass'] for c in twin['cases']], [False, True])
            self.assertEqual([c['proposal_false'] for c in twin['cases']], [False, True])
            self.assertIsNone(twin['result']['answer'])
            self.assertFalse(twin['result']['qualified'])

    def test_structural_success_does_not_overwrite_semantic_failure(self):
        r = report()
        self.assertEqual((r['counts']['passed'], r['counts']['cases'], r['counts']['false_unique']), (36, 36, 0))
        self.assertEqual(r['structural_quality_status'], 'PASS')
        self.assertEqual(r['semantic_quality_status'], 'FAIL')
        self.assertEqual(r['reply_role_counts'], dict(cases=4, passed=2, false_answers=0))
        self.assertEqual(r['unsafe_evaluator_comparator']['false_answers'], 2)
        summary = compact_report(r)
        self.assertEqual(summary['reply_role_counts'], r['reply_role_counts'])
        self.assertEqual(len(summary['full_report_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
