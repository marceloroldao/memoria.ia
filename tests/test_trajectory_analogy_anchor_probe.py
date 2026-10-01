from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_analogy_anchor_probe import evaluate, checked_shadow, internal_anchors
from trajectory_analogy_frame_probe import learn_frames
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


class AnchorShadowTests(unittest.TestCase):
    def test_mixed_relation_is_vetoed_with_original_evidence_preserved(self):
        for case in evaluate(20261018, 'varying_tag')['cases'][:2]:
            self.assertTrue(case['quality_pass'])
            self.assertIsNone(case['result']['hypothesis'])
            self.assertTrue(case['result']['baseline']['hypothesis'])
            self.assertTrue(case['result']['blocked_frames'][0]['anchors'])
            self.assertEqual(len(case['result']['blocked_frames'][0]['witnesses']), 3)

    def test_invariant_and_plain_positive_controls_remain_answered(self):
        for family in ('baseline', 'invariant_tag'):
            self.assertTrue(all(c['quality_pass'] for c in evaluate(20261018, family)['cases']))

    def test_renaming_preserves_decisions_and_anchor_positions(self):
        a, b = evaluate(20261018, 'varying_tag'), evaluate(20261018, 'varying_tag', True)
        for x, y in zip(a['cases'], b['cases']):
            self.assertEqual(x['quality_pass'], y['quality_pass'])
            xa = x['result']['blocked_frames'][0]['anchors'][0]
            ya = y['result']['blocked_frames'][0]['anchors'][0]
            self.assertEqual(xa['positions'], ya['positions'])
            self.assertEqual(tuple(1000000-s for s in xa['symbols']), ya['symbols'])

    def test_coincidental_internal_anchor_loses_a_legitimate_answer(self):
        memory = TrajectoryGenerationExperiment()
        for i in range(3):
            memory.observe((1, 10+i, 2), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe((3, 10+i, 4, 20+i, 8, 30+i, 5),
                           observation_id=f'{i}:t', stream_id=str(i))
        fact = (3, 13, 4, 23, 8, 33, 5)
        memory.observe(fact, observation_id='fact', stream_id='fact')
        result = checked_shadow(memory, (1, 13, 2))
        self.assertEqual(result['baseline']['hypothesis'], fact)
        self.assertIsNone(result['hypothesis'])
        self.assertEqual(result['blocked_frames'][0]['anchors'][0]['symbols'], (8,))

    def test_repeated_anchor_retains_all_positions(self):
        memory = TrajectoryGenerationExperiment()
        for i in range(3):
            memory.observe((1, 10+i, 2), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe((3, 10+i, 4, 20+i, 8, 30+i, 8, 40+i, 5),
                           observation_id=f'{i}:t', stream_id=str(i))
        anchors = internal_anchors(memory, learn_frames(memory)[0])
        self.assertEqual(anchors, ({'symbols': (8,), 'positions': ((1, 3),)*3},))
