from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_evidence_packet_probe import checked_packet, intervention, probe
from trajectory_analogy_fixed_context_probe import control_fixture
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


class EvidencePacketTests(unittest.TestCase):
    def test_new_sequence_evidence_without_new_payload_or_repeat_vote(self):
        stages = intervention(20261108)['stages']
        self.assertEqual([s['packet']['distinct_continuation_roots'] for s in stages], [0,0,0,1,1,2])
        self.assertEqual([s['packet']['continuation_occurrences'] for s in stages], [0,0,0,1,2,3])
        self.assertEqual(stages[2]['unique_payloads'], stages[-1]['unique_payloads'])
        self.assertEqual(stages[-1]['packet']['structural_status'], 'CONFLICT')

    def test_same_inputs_cannot_reveal_evaluators_hidden_roles(self):
        report = probe(20261107)
        a,b = report['observationally_equivalent_contracts']
        self.assertNotEqual(a['evaluator_contract'],b['evaluator_contract'])
        self.assertEqual(a['packet'],b['packet'])
        self.assertEqual(report['semantic_quality_status'],'UNRESOLVED')
        self.assertIsNone(a['packet']['answer'])
        self.assertFalse(a['packet']['qualified'])

    def test_never_skips_intermediate_observation_or_joins_captures(self):
        memory=TrajectoryGenerationExperiment()
        for value,oid,scope in (((1,2),'q','one'),((8,9),'middle','one'),((5,6),'later','one'),
                                ((1,2),'other-q','two'),((7,8),'other-a','three')):
            memory.observe(value,observation_id=oid,stream_id=scope)
        result=checked_packet(memory,(1,2))
        self.assertEqual([c['output'] for c in result['observed_continuations']],[(8,9)])
        self.assertEqual(result['observed_continuations'][0]['witnesses'][0]['target_observation_id'],'middle')

    def test_hierarchy_is_part_of_sequence_scope(self):
        memory=TrajectoryGenerationExperiment()
        memory.observe((1,2),observation_id='q',stream_id='same',hierarchy_id='a')
        memory.observe((3,4),observation_id='a',stream_id='same',hierarchy_id='b')
        self.assertFalse(checked_packet(memory,(1,2))['observed_continuations'])

    def test_exact_query_required_and_frame_candidates_preserved(self):
        memory,query,fact,_=control_fixture(20261107,'whole_tail')
        memory.observe(query,observation_id='q',stream_id='direct')
        memory.observe(fact,observation_id='a',stream_id='direct')
        result=checked_packet(memory,query)
        self.assertEqual({c['output'] for c in result['candidates']},{fact})
        self.assertEqual(result['candidates'][0]['evidence_kinds'],['FRAME_MATCH','EXACT_OBSERVED_CONTINUATION'])
        self.assertFalse(checked_packet(memory,(999,)+query)['observed_continuations'])

    def test_bijective_renaming_preserves_status_and_no_authorization(self):
        a,b=intervention(20261107),intervention(20261107,True)
        for x,y in zip(a['stages'],b['stages']):
            left,right=x['packet'],y['packet']
            self.assertEqual(left['structural_status'],right['structural_status'])
            self.assertEqual({tuple(1000000-z for z in c['output']) for c in left['candidates']},
                             {c['output'] for c in right['candidates']})
            self.assertFalse(left['qualified'])
            self.assertFalse(right['qualified'])


if __name__ == '__main__':
    unittest.main()
