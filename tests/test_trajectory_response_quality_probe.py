from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("response_quality_probe", ROOT / "scripts/trajectory_response_quality_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

from memoria_resolutiva.trajectory_generation_v2 import GenerationCandidate, GenerationResult


class MemoryDouble:
    def __init__(self, result):
        self.result = result
        self.queries = []

    def snapshot(self):
        return {"inputs": 2}

    def learning_state(self):
        return {"relations": 1}

    def generate(self, query):
        self.queries.append(query)
        return self.result


def result(mode, outputs):
    candidates = tuple(GenerationCandidate(tuple(output), (), 0.0, "observed_end", ())
                       for output in outputs)
    return GenerationResult(mode, candidates, len(outputs) > 1, False, 0)


class ResponseQualityScoringTests(unittest.TestCase):
    def check(self, generated, kind, expected=(), adapter="unicode"):
        memory = MemoryDouble(generated)
        descriptor = dict(name="control", query="Q?", expected=expected, kind=kind, required=True)
        row = probe.evaluate_case(memory, memory, descriptor, adapter)
        self.assertEqual(memory.queries, [probe.encode("Q?", adapter)] * 2)
        return row

    def test_echo_is_not_counted_as_a_correct_answer(self):
        row = self.check(result("ECHO", [map(ord, "Q?")]), "answer", ("Q?",))
        self.assertFalse(row["selected_correct"])
        self.assertFalse(row["quality_pass"])
        absence = self.check(result("ECHO", [map(ord, "Q?")]), "absence")
        self.assertTrue(absence["quality_pass"])
        self.assertFalse(absence["false_unique"])

    def test_wrong_unique_fragment_is_visible_in_absence_control(self):
        row = self.check(result("NODULE_RECALL", [map(ord, "other subject")]), "absence")
        self.assertTrue(row["false_unique"])
        self.assertFalse(row["quality_pass"])

    def test_retained_target_is_distinct_from_a_selected_answer(self):
        row = self.check(result("NODULE_RECALL", [map(ord, "context: correct"),
                                                 map(ord, "context fragment")]),
                         "answer", ("correct",))
        self.assertEqual(row["targets_retained"], [True])
        self.assertFalse(row["selected_correct"])
        self.assertFalse(row["quality_pass"])

    def test_conflicting_observed_outputs_require_both_targets_and_abstention(self):
        row = self.check(result("TEMPORAL_RECALL", [map(ord, "one"), map(ord, "two")]),
                         "conflict", ("one", "two"))
        self.assertTrue(row["quality_pass"])
        missing = self.check(result("TEMPORAL_RECALL", [map(ord, "one"), map(ord, "other")]),
                             "conflict", ("one", "two"))
        self.assertFalse(missing["quality_pass"])

    def test_invalid_utf8_output_is_reported_without_becoming_correct(self):
        row = self.check(result("CONTINUATION", [(0xC3,)]), "answer", ("á",), adapter="utf8")
        self.assertEqual(row["invalid_output_count"], 1)
        self.assertFalse(row["selected_correct"])


if __name__ == "__main__":
    unittest.main()
