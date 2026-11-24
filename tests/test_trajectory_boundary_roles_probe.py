from functools import lru_cache
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_boundary_roles_probe import probe,fingerprint


@lru_cache(maxsize=1)
def report():
    return probe(20261118)


class BoundaryRoleTests(unittest.TestCase):
    def test_reply_failures_remain_explicit_and_separate_from_integrity(self):
        r=report()
        self.assertEqual((r['diagnostic_passed'],r['diagnostic_cases']),(12,12))
        self.assertEqual(r['actual_reader_counts'],dict(cases=24,passed=12,positive_cases=12,
            correct_answers=0,negative_cases=12,correct_abstentions=12,false_answers=0))
        self.assertEqual(r['semantic_quality_status'],'FAIL')
        self.assertEqual(r['previous_structural_quality'],dict(passed=98,cases=126,status='FAIL',recomputed=False))

    def test_independent_twins_are_identical_even_with_complete_agreement(self):
        for ev in report()['evaluations']:
            self.assertNotEqual(ev['contracts'][0]['expected_answer'],ev['contracts'][1]['expected_answer'])
            for stage in ev['stages']:
                self.assertTrue(stage['observations_identical'])
                self.assertTrue(stage['packets_identical'])
                self.assertEqual(*stage['twin_snapshot_fingerprints'])
                self.assertEqual(*stage['twin_packet_fingerprints'])
                self.assertEqual(fingerprint(stage['packet']),stage['twin_packet_fingerprints'][0])
                self.assertTrue(all(f['coverage']=='COMPLETE' for f in stage['support']['frames']))
            self.assertTrue(all(f['unanimous_single_root'] for s in ev['stages'][:-1] for f in s['support']['frames']))

    def test_exact_continuations_keep_addresses_and_do_not_expose_hidden_roles(self):
        for ev in report()['evaluations']:
            self.assertEqual([len(s['packet']['observed_continuations']) for s in ev['stages']],[0,0,0,1,1,2])
            self.assertEqual([s['continuation_occurrences'] for s in ev['stages']],[0,0,0,1,2,3])
            for stage in ev['stages']:
                rows={r['observation_id']:r for r in stage['provenance']}
                roots={r['payload_id'] for r in rows.values()}
                self.assertTrue({c['payload_id'] for c in stage['packet']['candidates']} <= roots)
                for continuation in stage['packet']['observed_continuations']:
                    for witness in continuation['witnesses']:
                        self.assertEqual(rows[witness['source_observation_id']]['stream_id'],witness['stream_id'])
                        self.assertEqual(rows[witness['target_observation_id']]['payload_id'],continuation['payload_id'])
                self.assertFalse(any('evaluator_contract' in row or 'role' in row for row in rows.values()))
            for stage in ev['stages'][:-1]:
                self.assertNotIn('rival:target',{r['observation_id'] for r in stage['provenance']})

    def test_repetition_adds_sequence_witnesses_without_turning_agreement_into_authority(self):
        for ev in report()['evaluations']:
            a,b,query_only,direct,repeated,last=ev['stages']
            self.assertEqual(a['packet'],b['packet'])
            self.assertEqual(b['packet'],query_only['packet'])
            roots=lambda s:{root for f in s['support']['frames'] for root in f['candidate_roots']}
            self.assertEqual(roots(direct),roots(repeated))
            self.assertTrue(roots(repeated)<roots(last))
            self.assertTrue({f['frame_id'] for f in direct['support']['frames']} <=
                            {f['frame_id'] for f in repeated['support']['frames']})
            self.assertTrue(all(not f['unanimous_single_root'] for f in last['support']['frames']))
            self.assertIsNone(last['packet']['prior_structural_hypothesis'])
            for stage in ev['stages']:
                self.assertIsNone(stage['packet']['answer'])
                self.assertFalse(stage['packet']['qualified'])

    def test_unsafe_comparator_is_evaluator_only_and_exposes_false_answers(self):
        self.assertEqual(report()['unsafe_evaluator_comparator_counts'],dict(cases=24,passed=12,
            correct_answers=10,correct_abstentions=2,false_answers=10))
        for ev in report()['evaluations']:
            for stage in ev['stages'][:-1]:
                positive,negative=stage['outcomes']
                self.assertTrue(positive['forced_consensus_pass'])
                self.assertTrue(negative['forced_consensus_false_answer'])
                self.assertEqual(positive['forced_consensus_proposal'],negative['forced_consensus_proposal'])
                self.assertIsNone(stage['packet']['answer'])

    def test_bijection_preserves_candidates_and_contract_outcomes(self):
        a,b=report()['evaluations']
        for x,y in zip(a['stages'],b['stages']):
            self.assertEqual({tuple(1000000-z for z in c['output']) for c in x['packet']['candidates']},
                             {c['output'] for c in y['packet']['candidates']})
            self.assertEqual(len(x['support']['frames']),len(y['support']['frames']))
            for p,q in zip(x['outcomes'],y['outcomes']):
                self.assertEqual(p['quality_pass'],q['quality_pass'])
                self.assertEqual(p['forced_consensus_false_answer'],q['forced_consensus_false_answer'])


if __name__=='__main__':
    unittest.main()
