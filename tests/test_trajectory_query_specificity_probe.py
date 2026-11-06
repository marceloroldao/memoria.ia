from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_query_specificity_probe import longest_shared_span, transfer_controls


class QuerySpecificityTests(unittest.TestCase):
    def test_disjoint_and_reversed_matches_do_not_cover_a_query(self):
        self.assertEqual(longest_shared_span((1, 2, 3, 4), (1, 2, 99, 3, 4)), 2)
        self.assertEqual(longest_shared_span((1, 2, 3), (3, 2, 1)), 1)

    def test_repetitions_preserve_positions(self):
        self.assertEqual(longest_shared_span((1, 1, 2), (90, 1, 1, 2, 91)), 3)
        self.assertEqual(longest_shared_span((1, 1, 2), (1, 2)), 2)
        self.assertEqual(longest_shared_span((1, 2), ()), 0)

    def test_threshold_ablation_loses_transfer_and_survives_symbol_renaming(self):
        rows = transfer_controls()
        self.assertEqual(rows[0]['vetoes'], rows[4]['vetoes'])
        self.assertFalse(rows[0]['vetoes']['0.5'])
        self.assertTrue(rows[0]['vetoes']['0.75'])
        self.assertTrue(rows[2]['vetoes']['0.25'])
        self.assertFalse(any(w['full_query'] for c in rows[0]['diagnostics']
                             for w in c['witnesses']))


if __name__ == '__main__':
    unittest.main()
