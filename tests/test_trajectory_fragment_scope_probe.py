from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_fragment_scope_probe import ShadowFragmentScope, unsupported_origin


class FragmentScopeProbeTests(unittest.TestCase):
    def test_unsupported_origin_exposes_the_rejected_contract_under_renaming(self):
        for adapter in ('unicode', 'utf8'):
            for renamed in (False, True):
                case = unsupported_origin(adapter, renamed)
                self.assertTrue(case['baseline_abstains'])
                self.assertFalse(case['contract_pass'])
                self.assertTrue(case['cold_parity'])
                self.assertTrue(case['learning_unchanged'])
                self.assertTrue(case['scoped_out_witnesses'])

    def test_multiple_complete_destinations_still_abstain(self):
        memory = ShadowFragmentScope()
        for i, answer in enumerate(((7, 8, 9), (17, 18, 19))):
            memory.observe((1, 2, 3, 4), observation_id=f'{i}:q', stream_id=str(i))
            memory.observe(answer, observation_id=f'{i}:a', stream_id=str(i))
        result = memory.contextual_route_hypothesis((1, 2, 3, 4))
        self.assertIsNone(result.hypothesis)
        self.assertEqual({c.output for c in result.generation.candidates},
                         {(7, 8, 9), (17, 18, 19)})

    def test_distinct_introduced_fragment_still_blocks_consolidation(self):
        memory = ShadowFragmentScope()
        for i, (query, answer) in enumerate((((1, 2, 3, 4), (17, 18, 19)),
                                            ((1, 2, 3, 5), (90, 7, 8, 9, 91)),
                                            ((1, 2, 3, 6), (92, 7, 8, 9, 93)))):
            memory.observe(query, observation_id=f'{i}:q', stream_id=str(i))
            memory.observe(answer, observation_id=f'{i}:a', stream_id=str(i))
        result = memory.contextual_route_hypothesis((1, 2, 3, 4))
        self.assertIsNone(result.hypothesis)
        self.assertIn((7, 8, 9), {c.output for c in result.generation.candidates})
