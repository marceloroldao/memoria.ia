from functools import lru_cache
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_separator_ablation_probe import probe,score


@lru_cache(maxsize=1)
def report():
    return probe(20261112)


class SeparatorAblationTests(unittest.TestCase):
    def test_denominators_and_unanswered_positives_remain_failures(self):
        r=report()
        self.assertEqual(r['counts']['cases'],126)
        self.assertEqual(r['counts']['passed'],94)
        self.assertEqual(r['structural_quality_status'],'FAIL')
        self.assertEqual(r['semantic_quality_status'],'UNQUALIFIED')
        self.assertEqual({k:v['passed'] for k,v in r['by_mode'].items()},
                         dict(explicit=42,absent=24,ambiguous=28))
        self.assertEqual(r['counts']['false_unique'],0)

    def test_only_sources_change_all_target_payloads_are_identical(self):
        for renamed in (False,True):
            modes=[ev for ev in report()['evaluations'] if ev['renamed']==renamed]
            a=modes[0]
            for b in modes[1:]:
                self.assertEqual([z for _,z in a['training_pairs']],[z for _,z in b['training_pairs']])
                self.assertEqual(a['isolated_facts'],b['isolated_facts'])
                self.assertEqual(a['rival'],b['rival'])
                for left,right in zip(a['stages'],b['stages']):
                    for x,y in zip(left['cases'],right['cases']):
                        self.assertEqual((x['name'],x['kind'],x['expected']),(y['name'],y['kind'],y['expected']))

    def test_ambiguous_splits_keep_roots_and_suspend_unique_hypothesis(self):
        for ev in report()['evaluations']:
            if ev['mode']!='ambiguous':
                continue
            for stage in ev['stages']:
                for case in stage['cases'][:3]:
                    result=case['packet']
                    self.assertTrue(case['targets_retained'])
                    self.assertIsNone(result['prior_structural_hypothesis'])
                    prior=result['frame_read']['prior_alignment']
                    self.assertTrue(prior['partial_alignment_support'])
                    support=prior['query_alignment_support']
                    self.assertTrue(any(x['candidate_roots'] for x in support))
                    self.assertTrue(any(not x['candidate_roots'] for x in support))

    def test_no_separator_loses_coverage_and_repetition_does_not_repair_it(self):
        for ev in report()['evaluations']:
            first,repeated,last=ev['stages']
            self.assertEqual(first['unique_payloads'],repeated['unique_payloads'])
            self.assertNotIn('rival',{r['observation_id'] for r in repeated['provenance']})
            for a,b in zip(first['cases'],repeated['cases']):
                self.assertEqual({c['output'] for c in a['packet']['candidates']},
                                 {c['output'] for c in b['packet']['candidates']})
                self.assertEqual(a['packet']['prior_structural_hypothesis'],b['packet']['prior_structural_hypothesis'])
            if ev['mode']=='absent':
                self.assertTrue(all(not c['packet']['candidates'] for s in ev['stages'] for c in s['cases']))

    def test_renaming_provenance_and_packets_stay_unqualified(self):
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
                    self.assertFalse(x['packet']['observed_continuations'])

    def test_conflict_scoring_rejects_selecting_one_supported_root(self):
        result=dict(candidates=[dict(output=(1,2)),dict(output=(3,4))],prior_structural_hypothesis=(1,2))
        r=score(result,'conflict',((1,2),(3,4)))
        self.assertTrue(r['targets_retained'])
        self.assertFalse(r['quality_pass'])
        self.assertTrue(r['false_unique'])
        result['prior_structural_hypothesis']=None
        self.assertTrue(score(result,'conflict',((1,2),(3,4)))['quality_pass'])


if __name__=='__main__':
    unittest.main()
