import unittest

from src.memoria_ia import ResolutiveMemory


class BaselineTests(unittest.TestCase):
    def test_deduplication(self):
        m = ResolutiveMemory()
        for _ in range(8):
            m.observe("earth", "planet")
        self.assertEqual(m.layers[0].entries[next(iter(m.layers[0].entries))].observations, 8)
        self.assertLess(m.footprint(), 8)

    def test_repeated_evidence_consolidates(self):
        m = ResolutiveMemory()
        for _ in range(16):
            m.observe("water", "H2O")
        recalled = m.recall("water")
        self.assertIsNotNone(recalled)
        self.assertEqual(recalled[0], "H2O")
        self.assertGreaterEqual(recalled[1], 16)

    def test_single_conflict_does_not_overwrite_deep_memory(self):
        m = ResolutiveMemory()
        for _ in range(32):
            m.observe("sky", "blue")
        before = m.recall("sky")
        m.observe("sky", "green")
        after = m.recall("sky")
        self.assertEqual(before, after)
        self.assertEqual(after[0], "blue")

    def test_uniform_clock_ablation_constructs(self):
        m = ResolutiveMemory(temporal_scaling=False)
        self.assertTrue(all(layer.update_period == 1 for layer in m.layers))


if __name__ == "__main__":
    unittest.main()
