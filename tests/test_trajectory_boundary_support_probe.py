from functools import lru_cache
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_boundary_support_probe import probe,summarize


@lru_cache(maxsize=1)
def report():
    return probe(20261116)


class BoundarySupportTests(unittest.TestCase):
    def test_diagnostics_are_separate_from_existing_quality_failures(self):
        r=report()
        self.assertEqual((r['diagnostic_passed'],r['diagnostic_cases']),(20,20))
        self.assertEqual(r['previous_structural_quality'],dict(passed=98,cases=126,status='FAIL',recomputed=False))
        self.assertEqual(r['semantic_quality_status'],'UNQUALIFIED')

    def test_repeat_changes_occurrences_without_votes_or_new_cuts(self):
        for ev in report()['evaluations']:
            first,repeated=ev['stages'][1:3]
            self.assertEqual(first['support'],repeated['support'])
            self.assertEqual(first['packet'],repeated['packet'])
            self.assertEqual(len(first['candidate_occurrences']),1)
            self.assertEqual(len(repeated['candidate_occurrences']),3)
            self.assertNotIn('rival',{r['observation_id'] for r in repeated['provenance']})

    def test_partial_and_complete_conflicts_preserve_all_observed_roots(self):
        for ev in report()['evaluations']:
            if ev['joined_target_copies']:
                continue
            stages=ev['stages']
            self.assertEqual([s['support']['frames'][0]['covered_cuts'] for s in stages],[0,1,1,1,2,3])
            self.assertEqual([len(s['support']['frames'][0]['candidate_roots']) for s in stages],[0,1,1,2,3,4])
            for a,b in zip(stages,stages[1:]):
                self.assertTrue(set(a['support']['frames'][0]['candidate_roots']) <=
                                set(b['support']['frames'][0]['candidate_roots']))
            self.assertFalse(any(f['unanimous_single_root'] for s in stages for f in s['support']['frames']))
            self.assertTrue(all(s['packet']['prior_structural_hypothesis'] is None for s in stages))

    def test_complete_agreement_is_revoked_by_rival_and_never_authorizes_answer(self):
        for ev in report()['evaluations']:
            if not ev['joined_target_copies']:
                continue
            first,repeated,rival=ev['stages'][1:]
            for stage in (first,repeated):
                self.assertTrue(all(f['unanimous_single_root'] for f in stage['support']['frames']))
            self.assertTrue(all(len(f['common_roots'])==2 and not f['unanimous_single_root']
                                for f in rival['support']['frames']))
        for ev in report()['evaluations']:
            for stage in ev['stages']:
                self.assertIsNone(stage['support']['answer'])
                self.assertFalse(stage['support']['qualified'])
                roots={row['payload_id'] for row in stage['provenance']}
                self.assertTrue({root for f in stage['support']['frames'] for root in f['candidate_roots']} <= roots)

    def test_common_root_does_not_hide_a_rival_or_an_unsupported_cut(self):
        cuts=[dict(frame_id='a',candidate_roots=roots) for roots in (('r',),('r','s'),('r',))]
        frame=summarize(dict(boundary_support=cuts))['frames'][0]
        self.assertEqual(frame['common_roots'],('r',))
        self.assertEqual(frame['root_relation'],'MULTIPLE_ROOTS')
        self.assertFalse(frame['unanimous_single_root'])
        cuts[-1]['candidate_roots']=()
        frame=summarize(dict(boundary_support=cuts))['frames'][0]
        self.assertEqual(frame['common_roots'],())
        self.assertEqual(frame['coverage'],'PARTIAL')
        self.assertEqual(summarize(dict(boundary_support=()))['frames'],())

    def test_bijection_preserves_coverage_and_observed_outputs(self):
        evaluations=report()['evaluations']
        for a,b in (evaluations[:2],evaluations[2:]):
            for x,y in zip(a['stages'],b['stages']):
                self.assertEqual(x['expected_coverage'],y['expected_coverage'])
                self.assertEqual(x['expected_root_relation'],y['expected_root_relation'])
                self.assertEqual({tuple(1000000-z for z in output) for output in x['expected_outputs']},set(y['expected_outputs']))
                self.assertEqual(summarize(x['packet']),x['support'])


if __name__=='__main__':
    unittest.main()
