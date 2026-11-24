from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_analogy_fixed_context_probe import checked, control_fixture, controls, probe
from trajectory_analogy_alignment_probe import checked as prior_checked
from trajectory_analogy_stress_probe import FAMILIES, fixture
from trajectory_analogy_unmarked_probe import fixture as unmarked_fixture
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


class FixedContextTests(unittest.TestCase):
    def test_recovers_specific_roots_and_conflicts_without_claiming_global_quality(self):
        r=probe(20261106)
        self.assertEqual(r['counts'],dict(cases=48,passed=40,answer_cases=16,correct_answers=8,
            conflict_cases=16,conflicts_preserved=16,absence_cases=16,absence_empty=16,false_unique=0))
        self.assertEqual(r['prior_counts']['passed'],32)
        self.assertEqual(r['prior_counts']['false_unique'],8)
        self.assertEqual(r['main_quality_status'],'FAIL')
        self.assertEqual(r['quality_status'],'FAIL')
        self.assertEqual(r['control_counts'],dict(cases=8,passed=4,false_unique=0))
        self.assertEqual(r['authorization_ablation']['counts']['passed'],48)
        self.assertEqual(r['authorization_ablation']['control_counts']['false_unique'],2)

    def test_hidden_role_contracts_remain_observationally_indistinguishable(self):
        a,b=controls(20261105,authorize_new_unique=True)[0],controls(20261105,authorize_new_unique=True)[2]
        for key in ('training_pairs','query','fact','result'):
            self.assertEqual(a[key],b[key])
        self.assertTrue(a['quality_pass'])
        self.assertFalse(b['quality_pass'])
        self.assertTrue(b['false_unique'])
        self.assertIsNone(b['result']['prior_alignment']['hypothesis'])
        memory,query,fact,_=control_fixture(20261105,'latent_relation')
        safe=checked(memory,query)
        self.assertEqual({c['output'] for c in safe['candidates']},{fact})
        self.assertIsNone(safe['hypothesis'])
        self.assertEqual(safe['reason'],'COPIED_CONTEXT_CANDIDATE_ONLY')

    def test_requires_copied_fixed_context_and_retains_internal_anchor_veto(self):
        cases=controls(20261105)
        absent,blocked=cases[4]['result'],cases[6]['result']
        self.assertFalse(absent['fixed_context_frames'])
        self.assertFalse(absent['candidates'])
        self.assertTrue(blocked['fixed_context_frames'])
        self.assertTrue(all(f['internal_anchors'] for f in blocked['fixed_context_frames']))
        self.assertFalse(blocked['candidates'])

    def test_rejects_root_with_a_second_copy_of_the_variable(self):
        memory,query,fact,_=control_fixture(20261105,'whole_tail')
        variable=query[3:4]
        corrupt=fact[:-1]+variable+fact[-1:]
        memory.observe(corrupt,observation_id='corrupt',stream_id='corrupt')
        r=checked(memory,query)
        self.assertEqual({c['output'] for c in r['candidates']},{fact})

    def test_old_stress_candidates_and_hypotheses_are_unchanged(self):
        for family in FAMILIES:
            pairs,facts,queries=fixture(20261026,family)
            memory=TrajectoryGenerationExperiment()
            for i,(q,a) in enumerate(pairs):
                memory.observe(q,observation_id=f'{i}:s',stream_id=str(i))
                memory.observe(a,observation_id=f'{i}:t',stream_id=str(i))
            for i,fact in enumerate(facts):
                memory.observe(fact,observation_id=f'fact:{i}',stream_id=f'fact:{i}')
            for _,query,_,_ in queries:
                old,new=prior_checked(memory,query),checked(memory,query)
                self.assertEqual(old['candidates'],new['candidates'],family)
                self.assertEqual(old['hypothesis'],new['hypothesis'],family)

    def test_prior_partial_alignment_is_not_promoted_to_an_answer(self):
        memory=TrajectoryGenerationExperiment()
        for i in range(3):
            memory.observe((1,10+i,7,20+i,2),observation_id=f'{i}:s',stream_id=str(i))
            memory.observe((3,10+i,4,20+i,30+i,5),observation_id=f'{i}:t',stream_id=str(i))
        memory.observe((3,13,7,14,4,23,33,5),observation_id='fact',stream_id='fact')
        result=checked(memory,(1,13,7,14,7,23,2))
        self.assertIsNone(result['hypothesis'])
        self.assertEqual(result['reason'],'PRIOR_PARTIAL_ALIGNMENT_SUPPORT')

    def test_renaming_preserves_matches_and_earlier_unmarked_failure_is_retained(self):
        a,b=controls(20261105)[0],controls(20261105)[1]
        self.assertEqual({tuple(1000000-x for x in c['output']) for c in a['result']['candidates']},
                         {c['output'] for c in b['result']['candidates']})
        self.assertIsNone(a['result']['hypothesis'])
        pairs,fact,queries=unmarked_fixture(20261028,'relation_two_no_anchor')
        memory=TrajectoryGenerationExperiment()
        for i,(q,t) in enumerate(pairs):
            memory.observe(q,observation_id=f'{i}:s',stream_id=str(i))
            memory.observe(t,observation_id=f'{i}:t',stream_id=str(i))
        memory.observe(fact,observation_id='fact',stream_id='fact')
        result=checked(memory,queries[0][1])
        self.assertEqual(result['hypothesis'],fact)
        self.assertFalse(result['fixed_context_matches'])
