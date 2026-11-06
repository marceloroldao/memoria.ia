from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_analogy_alignment_probe import alignment_controls, checked, evaluate, probe
from trajectory_analogy_unmarked_probe import fixture
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


class AlignmentConsensusTests(unittest.TestCase):
    def test_partial_support_retains_root_without_authorizing_unique_answer(self):
        case = alignment_controls(20261101)[0]
        self.assertTrue(case['quality_pass'])
        result = case['result']
        self.assertEqual(len(result['candidates']), 1)
        self.assertIsNone(result['hypothesis'])
        self.assertFalse(result['prior_two_slot']['candidates'])
        self.assertTrue(result['partial_alignment_support'])
        self.assertEqual(sorted(len(a['candidate_roots']) for a in result['query_alignment_support']), [0,1])

    def test_different_splits_retain_two_competing_whole_roots(self):
        case = alignment_controls(20261101)[1]
        self.assertTrue(case['quality_pass'])
        result = case['result']
        self.assertEqual(len(result['candidates']), 2)
        self.assertIsNone(result['hypothesis'])
        self.assertFalse(result['partial_alignment_support'])
        self.assertEqual(len({a['candidate_roots'] for a in result['query_alignment_support']}), 2)

    def test_all_splits_agree_on_one_observed_root(self):
        case = alignment_controls(20261101)[2]
        result = case['result']
        self.assertTrue(case['quality_pass'])
        self.assertEqual(result['hypothesis'], case['expected'][0])
        self.assertIsNone(result['prior_two_slot']['hypothesis'])
        self.assertEqual(len(result['candidates'][0]['alignment_matches']), 2)
        self.assertEqual(len({a['candidate_roots'] for a in result['query_alignment_support']}), 1)

    def test_new_root_changes_partial_support_into_conflict_without_erasing_first(self):
        memory = TrajectoryGenerationExperiment()
        for i in range(3):
            memory.observe((1,10+i,7,20+i,2), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe((3,10+i,4,20+i,30+i,5), observation_id=f'{i}:t', stream_id=str(i))
        query = (1,13,7,14,7,23,2)
        a, z = (3,13,4,14,7,23,34,5), (3,13,7,14,4,23,33,5)
        memory.observe(z, observation_id='z', stream_id='z')
        first = checked(memory, query)
        self.assertEqual(first['reason'], 'PARTIAL_ALIGNMENT_SUPPORT')
        memory.observe(a, observation_id='a', stream_id='a')
        second = checked(memory, query)
        self.assertEqual({c['output'] for c in second['candidates']}, {a,z})
        self.assertIsNone(second['hypothesis'])

    def test_old_quality_denominator_and_failures_are_preserved(self):
        report = probe(20261102)
        self.assertEqual(report['counts']['passed'], 66)
        self.assertEqual(report['counts']['false_unique'], 0)
        self.assertEqual(report['alignment_control_status'], 'PASS')
        for case in evaluate(20261101, 'ambiguous_separator')['cases'][:3]:
            self.assertFalse(case['quality_pass'])
            self.assertEqual(len(case['result']['candidates']), 1)
            self.assertIsNone(case['result']['hypothesis'])

    def test_renaming_keeps_candidates_status_and_empty_control(self):
        a, b = alignment_controls(20261101), alignment_controls(20261101, True)
        for x,y in zip(a,b):
            self.assertEqual(x['result']['reason'], y['result']['reason'])
            self.assertEqual({tuple(1000000-s for s in c['output']) for c in x['result']['candidates']},
                             {c['output'] for c in y['result']['candidates']})
        self.assertFalse(a[3]['result']['candidates'])

    def test_unmarked_field_failure_remains_and_is_not_called_alignment_consensus(self):
        pairs,fact,queries = fixture(20261028, 'relation_two_no_anchor')
        memory = TrajectoryGenerationExperiment()
        for i,(s,t) in enumerate(pairs):
            memory.observe(s, observation_id=f'{i}:s', stream_id=str(i))
            memory.observe(t, observation_id=f'{i}:t', stream_id=str(i))
        memory.observe(fact, observation_id='fact', stream_id='fact')
        result = checked(memory, queries[0][1])
        self.assertEqual(result['hypothesis'], fact)
        self.assertEqual(result['reason'], 'PRIOR_SELECTOR_HYPOTHESIS_ONLY')
        self.assertFalse(result['query_alignment_support'])
