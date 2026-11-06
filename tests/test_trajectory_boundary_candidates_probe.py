from functools import lru_cache
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_boundary_candidates_probe import checked_boundary_packet,probe
from trajectory_response_quality_probe import TrajectoryGenerationExperiment
from trajectory_analogy_unmarked_probe import fixture as unmarked_fixture


@lru_cache(maxsize=1)
def report():
    return probe(20261114)


class BoundaryCandidateTests(unittest.TestCase):
    def test_candidate_gain_preserves_unanswered_quality_failures(self):
        r=report()
        self.assertEqual(r['counts'],dict(cases=126,passed=98,answer_cases=42,correct_answers=14,
            conflict_cases=12,conflicts_preserved=12,absence_cases=72,absence_empty=72,
            target_cases=54,all_targets_retained=54,false_unique=0))
        self.assertEqual(r['structural_quality_status'],'FAIL')
        self.assertEqual(r['by_mode']['absent']['correct_answers'],0)
        self.assertEqual(r['by_mode']['absent']['all_targets_retained'],18)

    def test_all_query_cuts_remain_visible_without_promoting_a_unique_root(self):
        for ev in report()['evaluations']:
            if ev['mode']!='absent':
                continue
            for stage in ev['stages']:
                for case in stage['cases'][:3]:
                    result=case['packet']
                    self.assertTrue(case['targets_retained'])
                    self.assertTrue(result['partial_boundary_support'])
                    self.assertIsNone(result['prior_structural_hypothesis'])
                    support=result['boundary_support']
                    self.assertTrue(any(x['candidate_roots'] for x in support))
                    self.assertTrue(any(not x['candidate_roots'] for x in support))
                    for frame_id in {x['frame_id'] for x in support}:
                        self.assertEqual(len([x for x in support if x['frame_id']==frame_id]),4)

    def test_prior_layout_candidates_and_hypotheses_stay_unchanged(self):
        for ev in report()['evaluations']:
            if ev['mode']=='absent':
                continue
            for stage in ev['stages']:
                for case in stage['cases']:
                    result=case['packet']; prior=result['inherited_packet']
                    self.assertEqual({c['output'] for c in result['candidates']},
                                     {c['output'] for c in prior['candidates']})
                    self.assertEqual(result['prior_structural_hypothesis'],prior['prior_structural_hypothesis'])

    def test_repeat_conflict_and_stage_provenance_do_not_erase_evidence(self):
        for ev in report()['evaluations']:
            first,repeated,last=ev['stages']
            self.assertEqual(first['unique_payloads'],repeated['unique_payloads'])
            self.assertNotIn('rival',{r['observation_id'] for r in repeated['provenance']})
            for a,b in zip(first['cases'],repeated['cases']):
                self.assertEqual({c['output'] for c in a['packet']['candidates']},
                                 {c['output'] for c in b['packet']['candidates']})
            for case in last['cases'][:2]:
                self.assertEqual({c['output'] for c in case['packet']['candidates']},set(case['expected']))
                self.assertIsNone(case['packet']['prior_structural_hypothesis'])

    def test_renaming_and_unqualified_packets_preserve_addressed_roots(self):
        for mode in ('explicit','absent','ambiguous'):
            a,b=[ev for ev in report()['evaluations'] if ev['mode']==mode]
            for left,right in zip(a['stages'],b['stages']):
                roots={r['payload_id'] for r in left['provenance']}
                for x,y in zip(left['cases'],right['cases']):
                    self.assertEqual(x['quality_pass'],y['quality_pass'])
                    self.assertEqual({tuple(1000000-z for z in c['output']) for c in x['packet']['candidates']},
                                     {c['output'] for c in y['packet']['candidates']})
                    self.assertTrue({c['payload_id'] for c in x['packet']['candidates']} <= roots)
                    self.assertIsNone(x['packet']['answer'])
                    self.assertFalse(x['packet']['qualified'])

    def test_reverse_copy_order_and_extra_copy_or_internal_anchor_controls(self):
        for anchored in (False,True):
            memory=TrajectoryGenerationExperiment()
            for i in range(3):
                a,b=(10+i,20+i),(30+i,40+i)
                memory.observe((1,)+a+b+(2,),observation_id=f'{i}:q',stream_id=str(i))
                tail=(60+i,99,70+i) if anchored else (60+i,)
                memory.observe((3,)+b+(4,)+a+(5,)+tail+(6,),observation_id=f'{i}:a',stream_id=str(i))
            a,b=(13,23),(33,43)
            query=(1,)+a+b+(2,)
            target=(3,)+b+(4,)+a+(5,)+((63,99,73) if anchored else (63,))+(6,)
            memory.observe(target,observation_id='fact',stream_id='fact')
            corrupt=target[:-1]+a+target[-1:]
            memory.observe(corrupt,observation_id='corrupt',stream_id='corrupt')
            result=checked_boundary_packet(memory,query)
            new={c['output'] for c in result['candidates'] if 'UNSEPARATED_COPY_MATCH' in c['evidence_kinds']}
            self.assertEqual(new,set() if anchored else {target})
            self.assertNotIn(corrupt,new)
            self.assertTrue(any(f['target_order']==(1,0) for f in result['boundary_frames']))
            self.assertIsNone(result['prior_structural_hypothesis'])

    def test_cross_capture_pairs_do_not_form_frames_and_old_failure_is_explicit(self):
        memory=TrajectoryGenerationExperiment()
        for i in range(3):
            memory.observe((1,10+i,20+i,2),observation_id=f'{i}:q',stream_id=f'{i}:q')
            memory.observe((3,10+i,4,20+i,5,30+i,6),observation_id=f'{i}:a',stream_id=f'{i}:a')
        self.assertFalse(checked_boundary_packet(memory,(1,13,23,2))['boundary_frames'])
        pairs,fact,queries=unmarked_fixture(20261028,'relation_two_no_anchor')
        memory=TrajectoryGenerationExperiment()
        for i,(q,a) in enumerate(pairs):
            memory.observe(q,observation_id=f'{i}:q',stream_id=str(i))
            memory.observe(a,observation_id=f'{i}:a',stream_id=str(i))
        memory.observe(fact,observation_id='fact',stream_id='fact')
        result=checked_boundary_packet(memory,queries[0][1])
        self.assertEqual(result['inherited_structural_hypothesis'],fact)
        self.assertEqual(result['prior_structural_hypothesis'],fact)
        self.assertFalse(result['qualified'])


if __name__=='__main__':
    unittest.main()
