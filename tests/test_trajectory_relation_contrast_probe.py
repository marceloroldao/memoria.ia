from functools import lru_cache
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_relation_contrast_probe import probe


@lru_cache(maxsize=2)
def report(seed=20261110):
    return probe(seed)


class RelationContrastTests(unittest.TestCase):
    def test_enriched_contract_and_separate_hidden_failures(self):
        r=report()
        self.assertEqual(r['counts'],dict(cases=40,passed=40,answer_cases=14,correct_answers=14,
            conflict_cases=2,conflicts_preserved=2,absence_cases=24,absence_empty=24,false_unique=0))
        self.assertEqual(r['stage_counts']['hidden_relation'],dict(cases=10,passed=6))
        self.assertEqual(r['stage_counts']['repeated_hidden_relation'],dict(cases=10,passed=6))
        self.assertEqual(r['cross_control_counts'],dict(cases=6,passed=6))
        self.assertEqual(r['all_stage_counts'],dict(cases=60,passed=52))
        self.assertEqual(r['structural_quality_status'],'FAIL')
        self.assertEqual(r['enriched_quality_status'],'PASS')
        self.assertEqual(r['semantic_quality_status'],'UNQUALIFIED')

    def test_identical_repetitions_do_not_unlock_missing_cue_routes(self):
        for ev in report()['evaluations']:
            first,repeated=ev['stages'][:2]
            self.assertEqual(first['unique_payloads'],repeated['unique_payloads'])
            for a,b in zip(first['cases'],repeated['cases']):
                self.assertEqual(a['packet']['candidates'],b['packet']['candidates'])
                self.assertEqual(a['packet']['prior_structural_hypothesis'],b['packet']['prior_structural_hypothesis'])

    def test_holdout_query_has_no_exact_continuation_and_uses_observed_roots(self):
        for ev in report()['evaluations']:
            for stage in ev['stages']:
                for case in stage['cases']:
                    packet=case['packet']
                    roots={r['payload_id'] for r in stage['provenance']}
                    self.assertFalse(packet['observed_continuations'])
                    self.assertTrue({c['payload_id'] for c in packet['candidates']} <= roots)
                    self.assertIsNone(packet['answer'])
                    self.assertFalse(packet['qualified'])

    def test_changing_value_retains_same_relation_conflict_and_other_relation(self):
        for ev in report()['evaluations']:
            prior,last=ev['stages'][-2:]
            first=last['cases'][0]
            self.assertEqual({c['output'] for c in first['packet']['candidates']},set(first['expected']))
            self.assertIsNone(first['packet']['prior_structural_hypothesis'])
            self.assertEqual(prior['cases'][1]['packet']['prior_structural_hypothesis'],
                             last['cases'][1]['packet']['prior_structural_hypothesis'])
            self.assertNotIn('rival',{r['observation_id'] for r in prior['provenance']})

    def test_crossed_observations_separate_cues_and_preserve_original(self):
        for ev in report()['evaluations']:
            for case in ev['cross_controls']:
                self.assertTrue(case['quality_pass'])
                self.assertEqual({c['output'] for c in case['packet']['candidates']},set(case['expected']))
            crossed,repeated=ev['stages'][3:5]
            self.assertEqual(crossed['unique_payloads'],repeated['unique_payloads'])
            for a,b in zip(crossed['cases'],repeated['cases']):
                self.assertEqual({c['output'] for c in a['packet']['candidates']},
                                 {c['output'] for c in b['packet']['candidates']})

    def test_bijective_renaming_preserves_outputs_and_quality(self):
        a,b=report()['evaluations']
        for left,right in zip(a['stages'],b['stages']):
            for x,y in zip(left['cases'],right['cases']):
                self.assertEqual(x['quality_pass'],y['quality_pass'])
                self.assertEqual({tuple(1000000-z for z in c['output']) for c in x['packet']['candidates']},
                                 {c['output'] for c in y['packet']['candidates']})


if __name__=='__main__':
    unittest.main()
