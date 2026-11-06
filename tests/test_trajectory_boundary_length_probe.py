from functools import lru_cache
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_boundary_length_probe import fixture, probe


@lru_cache(maxsize=1)
def report():
    return probe(20261124)


class BoundaryLengthTests(unittest.TestCase):
    def test_lengths_are_crossed_and_target_ablation_preserves_sources(self):
        for varied in (False, True):
            a, b = [fixture(20261124, varied, joined) for joined in (False, True)]
            self.assertEqual([q for q, _ in a['training_pairs']], [q for q, _ in b['training_pairs']])
            self.assertEqual(a['queries'], b['queries'])
            self.assertEqual(a['reserved_cut'], b['reserved_cut'])
            self.assertNotEqual(a['fact'], b['fact'])
        self.assertEqual(set(a['lengths']), {(1, 2), (1, 4), (3, 2), (3, 4)})

    def test_varied_lengths_do_not_remove_unsupported_query_cuts(self):
        for ev in report()['evaluations']:
            if ev['joined_target_copies']:
                continue
            for stage in ev['stages'][:3]:
                packet = stage['cases'][0]['packet']
                self.assertEqual({c['output'] for c in packet['candidates']}, {ev['fixture']['fact']})
                self.assertTrue(packet['partial_boundary_support'])
                self.assertIsNone(packet['prior_structural_hypothesis'])
                for f in stage['cases'][0]['support']['frames']:
                    self.assertEqual((f['total_cuts'], f['covered_cuts']), (4, 1))
                self.assertEqual({cut['source_position'] for cut in packet['boundary_support'] if cut['candidate_roots']},
                                 {ev['fixture']['reserved_cut']})

    def test_adjacent_copy_agreement_does_not_identify_a_unique_cut(self):
        for ev in report()['evaluations']:
            if not ev['joined_target_copies']:
                continue
            for stage in ev['stages'][:3]:
                case = stage['cases'][0]
                self.assertEqual(case['packet']['prior_structural_hypothesis'], ev['fixture']['fact'])
                self.assertEqual({cut['source_position'] for cut in case['packet']['boundary_support'] if cut['candidate_roots']},
                                 {2, 3, 4, 5})
                self.assertTrue(all(f['unanimous_single_root'] for f in case['support']['frames']))
                self.assertIsNone(case['packet']['answer'])
                self.assertFalse(case['packet']['qualified'])

    def test_repetition_adds_witnesses_without_layouts_or_candidates(self):
        for ev in report()['evaluations']:
            before, after = ev['stages'][:2]
            self.assertEqual(before['unique_payloads'], after['unique_payloads'])
            self.assertEqual(before['distinct_layouts'], after['distinct_layouts'])
            self.assertGreater(len(after['cases'][0]['packet']['boundary_frames']), len(before['cases'][0]['packet']['boundary_frames']))
            for a, b in zip(before['cases'], after['cases']):
                self.assertEqual({c['output'] for c in a['packet']['candidates']}, {c['output'] for c in b['packet']['candidates']})
                self.assertEqual(a['packet']['prior_structural_hypothesis'], b['packet']['prior_structural_hypothesis'])

    def test_different_cut_rival_keeps_both_roots_and_suspends_hypothesis(self):
        for ev in report()['evaluations']:
            c = ev['stages'][-1]['cases'][0]
            self.assertTrue(c['quality_pass'])
            self.assertEqual({x['output'] for x in c['packet']['candidates']}, {ev['fixture']['fact'], ev['fixture']['rival']})
            self.assertIsNone(c['packet']['prior_structural_hypothesis'])
            if not ev['joined_target_copies']:
                self.assertEqual({cut['source_position'] for cut in c['packet']['boundary_support'] if cut['candidate_roots']},
                                 {ev['fixture']['reserved_cut'], ev['fixture']['rival_cut']})

    def test_sources_cold_checks_and_bijection_remain_unqualified(self):
        evaluations = report()['evaluations']
        for left, right in zip(evaluations[::2], evaluations[1::2]):
            for a, b in zip(left['stages'], right['stages']):
                roots = {row['payload_id'] for row in a['provenance']}
                for ac, bc in zip(a['cases'], b['cases']):
                    self.assertEqual(ac['quality_pass'], bc['quality_pass'])
                    self.assertEqual({tuple(1000000 - z for z in x['output']) for x in ac['packet']['candidates']},
                                     {x['output'] for x in bc['packet']['candidates']})
                    self.assertTrue({x['payload_id'] for x in ac['packet']['candidates']} <= roots)
                    self.assertFalse(ac['packet']['observed_continuations'])
                    self.assertFalse(ac['packet']['qualified'])
                    self.assertIsNone(ac['packet']['answer'])

    def test_reserved_scorecard_preserves_quality_failure(self):
        r = report()
        self.assertEqual((r['counts']['passed'], r['counts']['cases'], r['counts']['correct_answers'],
                          r['counts']['all_targets_retained'], r['counts']['false_unique']), (148, 160, 12, 32, 0))
        self.assertEqual(r['structural_quality_status'], 'FAIL')
        self.assertEqual(r['semantic_quality_status'], 'UNQUALIFIED')
        self.assertEqual([v['passed'] for v in r['by_shape'].values()], [34, 40, 34, 40])


if __name__ == '__main__':
    unittest.main()
