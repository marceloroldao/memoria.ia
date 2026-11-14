from functools import lru_cache
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_observed_context_probe import probe


@lru_cache(maxsize=1)
def report():
    return probe(20261120)


class ObservedContextTests(unittest.TestCase):
    def test_initial_failures_are_preserved_separately_from_enriched_success(self):
        r=report()
        self.assertEqual(r['counts'],dict(cases=70,passed=64,answer_cases=28,correct_answers=22,
            conflict_cases=2,conflicts_preserved=2,absence_cases=40,absence_empty=40,
            target_cases=30,all_targets_retained=24,false_unique=0))
        self.assertEqual((r['enriched_counts']['passed'],r['enriched_counts']['cases']),(56,56))
        self.assertEqual((r['cross_control_counts']['passed'],r['cross_control_counts']['cases']),(6,6))
        self.assertEqual(r['structural_quality_status'],'FAIL')
        self.assertEqual(r['semantic_quality_status'],'UNQUALIFIED')
        self.assertEqual(r['previous_role_twins_quality']['status'],'FAIL')
        self.assertEqual(r['previous_structural_quality']['passed'],98)

    def test_only_source_payloads_are_added_when_context_first_becomes_transportable(self):
        for ev in report()['evaluations']:
            data=ev['fixture']; before,after=ev['stages'][:2]
            self.assertEqual([a for _,a in data['initial_pairs']],[a for _,a in data['transported_pairs']])
            roots_before={r['payload_id'] for r in before['provenance']}
            roots_after={r['payload_id'] for r in after['provenance']}
            self.assertEqual(len(roots_after-roots_before),3)
            for case in before['cases'][:3]:
                self.assertFalse(case['quality_pass'])
            for case in after['cases'][:3]:
                self.assertEqual({c['output'] for c in case['packet']['candidates']},set(case['expected']))
                self.assertTrue(case['quality_pass'])

    def test_context_alone_changes_route_and_uncopied_destination_is_excluded(self):
        for ev in report()['evaluations']:
            # First three queries have the same four-symbol body and different two-symbol contexts.
            queries=[q for _,q in ev['fixture']['queries'][:3]]
            self.assertEqual(len({q[-5:] for q in queries}),1)
            self.assertEqual(len({q[1:3] for q in queries}),3)
            stripped=ev['fixture']['facts'][3]
            for stage in ev['stages'][1:]:
                roots=[{c['payload_id'] for c in case['packet']['candidates']} for case in stage['cases'][:3]]
                self.assertTrue(all(not a&b for i,a in enumerate(roots) for b in roots[i+1:]))
                self.assertNotIn(stripped,{c['output'] for case in stage['cases'] for c in case['packet']['candidates']})
                for case in stage['cases'][3:]:
                    self.assertFalse(case['packet']['candidates'])

    def test_crossed_context_body_and_value_controls_retain_competitors(self):
        for ev in report()['evaluations']:
            changed,body,original=ev['cross_controls']
            self.assertEqual(len(changed['packet']['candidates']),2)
            self.assertIsNone(changed['packet']['prior_structural_hypothesis'])
            self.assertTrue(all(case['quality_pass'] for case in (changed,body,original)))
            self.assertNotEqual(body['expected'],original['expected'])

    def test_repetition_and_rival_preserve_stage_addresses_without_authorization(self):
        for ev in report()['evaluations']:
            crossed,repeated,last=ev['stages'][2:]
            self.assertEqual(crossed['unique_payloads'],repeated['unique_payloads'])
            for a,b in zip(crossed['cases'],repeated['cases']):
                self.assertEqual({c['output'] for c in a['packet']['candidates']},
                                 {c['output'] for c in b['packet']['candidates']})
                self.assertEqual(a['packet']['prior_structural_hypothesis'],b['packet']['prior_structural_hypothesis'])
            self.assertNotIn('rival',{r['observation_id'] for r in repeated['provenance']})
            self.assertEqual(len(last['cases'][0]['packet']['candidates']),2)
            self.assertIsNone(last['cases'][0]['packet']['prior_structural_hypothesis'])
            for stage in ev['stages']:
                roots={r['payload_id'] for r in stage['provenance']}
                for case in stage['cases']:
                    self.assertTrue({c['payload_id'] for c in case['packet']['candidates']} <= roots)
                    self.assertIsNone(case['packet']['answer'])
                    self.assertFalse(case['packet']['qualified'])
                    self.assertFalse(case['packet']['observed_continuations'])

    def test_bijection_preserves_structural_results_and_copied_roots(self):
        a,b=report()['evaluations']
        for x,y in zip(a['stages'],b['stages']):
            for p,q in zip(x['cases'],y['cases']):
                self.assertEqual(p['quality_pass'],q['quality_pass'])
                self.assertEqual({tuple(1000000-z for z in c['output']) for c in p['packet']['candidates']},
                                 {c['output'] for c in q['packet']['candidates']})


if __name__=='__main__':
    unittest.main()
