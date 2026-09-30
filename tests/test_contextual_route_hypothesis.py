from dataclasses import asdict
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_contextual_hypothesis_probe import positive_controls, read
from trajectory_response_quality_probe import TrajectoryGenerationExperiment, encode


def wrapped(rename=False):
    memory = TrajectoryGenerationExperiment()
    transform = lambda text: tuple(10000 - x if rename else x for x in encode(text, 'unicode'))
    query, answer = 'Código de Daro?', 'Daro: 791.'
    for i in range(3):
        memory.observe(transform(f'r{i}: {query}'), observation_id=f'{i}:s', stream_id=str(i))
        memory.observe(transform(f'r{i}: {answer}'), observation_id=f'{i}:t', stream_id=str(i))
    return memory, transform(query), transform(answer), transform


class ContextualRouteHypothesisTests(unittest.TestCase):
    def test_same_destination_context_yields_provisional_answer_without_erasing_routes(self):
        memory, query, answer, transform = wrapped()
        baseline = asdict(memory.generate(query))
        self.assertIsNone(memory.generate(query).selected)
        result = read(memory, query)
        self.assertEqual(result.reason, 'SHARED_DESTINATION_CONTEXT')
        self.assertEqual(result.hypothesis, transform(': ') + answer)
        self.assertEqual(result.shared_source_contexts, (query,))
        self.assertTrue(result.contextual_fragments)
        self.assertEqual(asdict(result.generation), baseline)
        self.assertIsNone(memory.generate(query).selected)
        self.assertEqual(read(memory, transform('Lembre: ') + query).hypothesis, result.hypothesis)

    def test_shared_fragment_of_another_subject_does_not_consolidate_the_answer(self):
        memory, _, _, transform = wrapped()
        result = read(memory, transform('Código de Neri?'))
        self.assertIsNone(result.hypothesis)
        self.assertEqual(result.reason, 'UNMATCHED_SHARED_SOURCE_CONTEXT')

    def test_different_observed_destinations_remain_competing(self):
        memory = TrajectoryGenerationExperiment()
        for i, answer in enumerate(['Daro: 791.', 'Daro: 415.']):
            memory.observe(encode('Código de Daro?', 'unicode'), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe(encode(answer, 'unicode'), observation_id=f'{i}:t', stream_id=str(i))
        result = read(memory, encode('Código de Daro?', 'unicode'))
        self.assertIsNone(result.hypothesis)
        outputs = {c.output for c in result.generation.candidates}
        self.assertIn(encode('Daro: 791.', 'unicode'), outputs)
        self.assertIn(encode('Daro: 415.', 'unicode'), outputs)

    def test_two_introduced_parts_of_one_destination_are_not_arbitrarily_chosen(self):
        memory = TrajectoryGenerationExperiment()
        for i in range(2):
            memory.observe((90+i, 1, 2, 3, 100+i), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe((200+i, 7, 8, 9, 600+i, 17, 18, 19, 300+i),
                           observation_id=f'{i}:t', stream_id=str(i))
        result = read(memory, (1000, 1, 2, 3, 1001))
        self.assertIsNone(result.hypothesis)
        self.assertEqual(result.reason, 'DISTINCT_DESTINATION_EVIDENCE')

    def test_limits_and_echo_do_not_become_an_answer(self):
        memory, query, _, _ = wrapped()
        result = memory.contextual_route_hypothesis(query, beam_width=1)
        self.assertTrue(result.generation.truncated)
        self.assertIsNone(result.hypothesis)
        empty = TrajectoryGenerationExperiment().contextual_route_hypothesis((1, 2, 3))
        self.assertIsNone(empty.hypothesis)
        self.assertEqual(empty.reason, 'ECHO_ONLY')

    def test_opaque_symbol_renaming_preserves_consolidation(self):
        original, query, _, _ = wrapped()
        renamed, renamed_query, _, _ = wrapped(rename=True)
        a, b = read(original, query), read(renamed, renamed_query)
        self.assertEqual(tuple(10000 - x for x in a.hypothesis), b.hypothesis)
        self.assertEqual(a.reason, b.reason)

    def test_all_existing_novel_carried_and_mixed_transfer_controls_survive(self):
        self.assertEqual(len(positive_controls()), 24)


if __name__ == '__main__':
    unittest.main()
