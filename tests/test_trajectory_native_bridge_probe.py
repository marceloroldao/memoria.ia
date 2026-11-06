from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_native_bridge_probe import adapt, fixtures, evaluate
from trajectory_response_quality_probe import encode


def row(text, sequence, scope='capture', kind='user_turn'):
    return dict(text=text, sequence=sequence, hierarchy_id=scope,
                source_id=f'{scope}:{sequence}', source_kind=kind)


class NativeBridgeAdapterTests(unittest.TestCase):
    def test_raw_symbols_preserve_case_accents_and_reuse_content(self):
        rows = [row('Áb', 1), row('áb', 2), row('Áb', 3)]
        for adapter in ('unicode', 'utf8'):
            memory, provenance = adapt(rows, adapter)
            self.assertEqual(len(provenance), 2)
            roots = {memory.expand(root): origins for root, origins in provenance.items()}
            self.assertEqual(len(roots[encode('Áb', adapter)]), 2)
            self.assertEqual(len(roots[encode('áb', adapter)]), 1)
            self.assertEqual(len(memory.snapshot()['observations']), 3)

    def test_assistant_barrier_prevents_skipping_to_later_user_reply(self):
        rows = [row('Q123?', 1), row('invented', 2, kind='assistant_generated'), row('A789.', 3)]
        for adapter in ('unicode', 'utf8'):
            memory, provenance = adapt(rows, adapter)
            self.assertEqual(len(provenance), 2)
            self.assertFalse(memory.temporal_neighbors(encode('Q123?', adapter)))
            self.assertNotIn(encode('invented', adapter), [memory.expand(root) for root in provenance])
            self.assertIsNone(memory.contextual_route_hypothesis(encode('Q123?', adapter)).hypothesis)

    def test_captures_do_not_create_a_reply_relation(self):
        memory, _ = adapt([row('Q123?', 1, 'one'), row('A789.', 1, 'two')], 'unicode')
        self.assertFalse(memory.temporal_neighbors(encode('Q123?', 'unicode')))
        self.assertIsNone(memory.contextual_route_hypothesis(encode('Q123?', 'unicode')).hypothesis)

    def test_duplicate_tied_or_reversed_sequences_are_rejected(self):
        for rows in ([row('A', 1), row('B', 1)], [row('A', 2), row('B', 1)],
                     [{**row('A', 1), 'sequence': True}],
                     [{**row('A', 1), 'source_kind': 'unknown'}]):
            with self.assertRaises(ValueError):
                adapt(rows, 'unicode')
        with self.assertRaises(ValueError):
            adapt([row('A', 1)], 'normalized_words')

    def test_native_question_tag_is_not_an_answer_label(self):
        memory, _ = adapt([row('Q123?', 1, kind='user_assertion')], 'unicode')
        result = memory.contextual_route_hypothesis(encode('Q123?', 'unicode'))
        self.assertEqual(result.generation.mode, 'ECHO')
        self.assertIsNone(result.hypothesis)


if __name__ == '__main__':
    unittest.main()
