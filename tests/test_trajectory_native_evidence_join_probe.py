import copy
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_native_evidence_join_probe import adapt_regions, join_evidence, probe
from trajectory_response_quality_probe import encode


def evidence():
    rows = [dict(hierarchy_id='conversation:a', source_id='q', sequence=1,
                 text='question', source_kind='user_turn', reply_to=None),
            dict(hierarchy_id='conversation:a', source_id='a', sequence=2,
                 text='first', source_kind='user_turn',
                 reply_to=dict(source_id='q', sequence=1)),
            dict(hierarchy_id='conversation:a', source_id='b', sequence=3,
                 text='rival', source_kind='user_turn', reply_to=None)]
    memory, origins = adapt_regions(rows)
    roots = {memory.expand(root): root for root in origins}
    first = roots[encode('first', 'unicode')]
    rival = roots[encode('rival', 'unicode')]
    structural = dict(packet=dict(query=encode('question', 'unicode'),
                                  candidates=[dict(payload_id=first), dict(payload_id=rival)]))
    linked = dict(answer=None, qualified=False, selection_used=False,
                  evidence_scope='exact_target', groups_truncated=False,
                  repeat_question_links=0, groups=[dict(
                      trail_address='native-address', representative_text='first',
                      sources_truncated=False, sources=[dict(
                          hierarchy_id='conversation:a', source_id='a', sequence=2,
                          question_source_id='q', question_sequence=1, text='first')])])
    return structural, origins, rows, linked, ('conversation:a', 'q', 1)


class EvidenceJoinTests(unittest.TestCase):
    def test_relation_annotation_retains_both_candidates_and_original_packet(self):
        args = evidence()
        before = copy.deepcopy(args)
        joined = join_evidence(*args)
        self.assertEqual(len(joined['candidates_with_provenance']), 2)
        self.assertEqual(len(joined['explicit_reply_relations']), 1)
        flags = [s['explicit_reply_to_selected_target'] for c in joined['candidates_with_provenance']
                 for s in c['occurrences']]
        self.assertEqual(flags, [True, False])
        self.assertEqual(joined['structural'], args[0])
        self.assertEqual(args, before)
        self.assertIsNone(joined['answer'])
        self.assertFalse(joined['qualified'])

    def test_linked_content_outside_frame_is_retained(self):
        args = list(evidence())
        outside = args[0]['packet']['candidates'].pop(0)['payload_id']
        joined = join_evidence(*args)
        self.assertEqual(joined['linked_roots_outside_structural_candidates'], [outside])
        self.assertEqual(len(joined['explicit_reply_relations']), 1)

    def test_forged_or_stale_origins_are_rejected(self):
        for mutation in ('root', 'reply_target', 'source_text', 'region', 'query'):
            args = list(evidence())
            if mutation == 'root':
                root = next(iter(args[1]))
                args[1]['forged'] = args[1].pop(root)
            elif mutation == 'reply_target':
                args[2][1]['reply_to']['sequence'] = 99
            elif mutation == 'source_text':
                args[3]['groups'][0]['sources'][0]['text'] = 'fabricated'
            elif mutation == 'region':
                args[4] = ('conversation:b', 'q', 1)
            else:
                args[0]['packet']['query'] = encode('other', 'unicode')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                join_evidence(*args)

    def test_incomplete_or_qualified_native_packet_is_rejected(self):
        for key, value in [('groups_truncated', True), ('repeat_question_links', 1),
                           ('qualified', True), ('answer', 'promoted'),
                           ('evidence_scope', 'matching_targets')]:
            args = list(evidence())
            args[3][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                join_evidence(*args)

    def test_raw_adapter_preserves_regions_and_generated_barriers_ignoring_links(self):
        rows = evidence()[2]
        rows.insert(2, dict(hierarchy_id='conversation:a', source_id='generated',
                            sequence=3, text='invented', source_kind='assistant_generated'))
        rows[3]['sequence'] = 4
        memory, origins = adapt_regions(rows)
        self.assertEqual({r['hierarchy_id'] for r in memory.snapshot()['observations']}, {'conversation:a'})
        self.assertNotIn(encode('invented', 'unicode'), [memory.expand(root) for root in origins])
        self.assertNotEqual(memory.snapshot()['observations'][1]['stream_id'],
                            memory.snapshot()['observations'][2]['stream_id'])
        other = copy.deepcopy(rows)
        other[1]['reply_to'] = None
        self.assertEqual(memory.snapshot(), adapt_regions(other)[0].snapshot())

    @unittest.skipUnless(os.environ.get('MEMORIA_NATIVE_LIBRARY'), 'requires native BDR library')
    def test_native_counterfactual_links_and_cold_join(self):
        for seed in (20261201, 20261202):
            with self.subTest(seed=seed):
                result = probe(Path(os.environ['MEMORIA_NATIVE_LIBRARY']), seed)
                self.assertEqual(result['integrity_passed'], 32)
                self.assertEqual(result['integrity_total'], 32)
                self.assertEqual(len({s['structural_sha256'] for s in result['stages']}), 1)


if __name__ == '__main__':
    unittest.main()
