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

    def test_observed_variant_uses_one_root_destination_without_changing_generation(self):
        memory = TrajectoryGenerationExperiment()
        for i, query in enumerate(('Código de Daro?', 'código de daro?')):
            memory.observe(encode(query, 'unicode'), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe(encode('Daro: 791.', 'unicode'), observation_id=f'{i}:t', stream_id=str(i))
        for query in ('código de daro?', 'Lembre: código de daro?'):
            result = read(memory, encode(query, 'unicode'))
            self.assertEqual(result.generation.mode, 'COMBINED_RECALL')
            self.assertIsNone(result.generation.selected)
            self.assertEqual(result.hypothesis, encode('Daro: 791.', 'unicode'))
            self.assertEqual(result.reason, 'OBSERVED_ROOT_DESTINATION_CONTEXT')
            self.assertTrue(result.contextual_fragments)
        for query in ('código de Neri?', 'Temperatura de Marte?'):
            self.assertIsNone(read(memory, encode(query, 'unicode')).hypothesis)

    def test_conserved_source_ending_preserves_opaque_identity_and_order(self):
        for renamed in (False, True):
            transform = lambda xs: tuple(10000 - x if renamed else x for x in xs)
            memory = TrajectoryGenerationExperiment()
            for i in range(2):
                memory.observe(transform((90+i, 1, 2, 3, 41+10*i, 42, 43)),
                               observation_id=f'{i}:s', stream_id=str(i))
                memory.observe(transform((94+i, 7, 8, 9, 96+i)),
                               observation_id=f'{i}:t', stream_id=str(i))
            self.assertEqual(read(memory, transform((1, 2, 3, 42, 43))).hypothesis,
                             transform((7, 8, 9)))
            absent = read(memory, transform((1, 2, 3, 62, 63)))
            self.assertIsNone(absent.hypothesis)
            self.assertIn(transform((42, 43)), absent.shared_source_contexts)
            self.assertIsNone(read(memory, transform((42, 43, 1, 2, 3))).hypothesis)

    def test_distinct_full_cues_scope_one_root_and_preserve_real_conflict(self):
        memory = TrajectoryGenerationExperiment()
        for i, (query, target) in enumerate((
            ('Código de Daro?', 'Daro: 791.'),
            ('código de daro?', 'Daro: 791.'),
            ('código de daro?', 'Daro: 415.'),
        )):
            memory.observe(encode(query, 'unicode'), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe(encode(target, 'unicode'), observation_id=f'{i}:t', stream_id=str(i))
        for query in ('Código de Daro?', 'código de daro?', 'Lembre: código de daro?'):
            result = read(memory, encode(query, 'unicode'))
            outputs = {c.output for c in result.generation.candidates}
            if query == 'Código de Daro?':
                self.assertEqual(result.hypothesis, encode('Daro: 791.', 'unicode'))
                self.assertEqual(result.reason, 'SOURCE_SCOPED_ROOT_DESTINATION')
                self.assertEqual(len(result.scoped_out_witnesses), 1)
                self.assertIsNone(result.generation.selected)
                self.assertTrue(result.generation.ambiguous)
                witness = result.scoped_out_witnesses[0]
                self.assertEqual(memory.expand(witness[0]), encode('código de daro?', 'unicode'))
                self.assertEqual(memory.expand(witness[1]), encode('Daro: 415.', 'unicode'))
            else:
                self.assertIsNone(result.hypothesis)
                self.assertIn(encode('Daro: 791.', 'unicode'), outputs)
                self.assertIn(encode('Daro: 415.', 'unicode'), outputs)

    def test_source_scope_requires_own_support_for_the_observed_root_destination(self):
        memory = TrajectoryGenerationExperiment()
        for i, (query, target) in enumerate((('Código de Daro?', 'Daro: 791.'),
                                           ('código de daro?', 'Daro: 415.'))):
            memory.observe(encode(query, 'unicode'), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe(encode(target, 'unicode'), observation_id=f'{i}:t', stream_id=str(i))
        result = read(memory, encode('Código de Daro?', 'unicode'))
        self.assertEqual(result.generation.mode, 'COMBINED_RECALL')
        self.assertIsNone(result.hypothesis)
        self.assertFalse(result.scoped_out_witnesses)

    def test_source_containing_the_full_root_cue_cannot_be_scoped_out(self):
        memory = TrajectoryGenerationExperiment()
        for i, (query, target) in enumerate((
            ('Código de Daro?', 'Daro: 791.'),
            ('extra: Código de Daro?', 'Daro: 791.'),
            ('extra: Código de Daro?', 'Daro: 415.'),
        )):
            memory.observe(encode(query, 'unicode'), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe(encode(target, 'unicode'), observation_id=f'{i}:t', stream_id=str(i))
        result = read(memory, encode('Código de Daro?', 'unicode'))
        self.assertIsNone(result.hypothesis)
        self.assertFalse(result.scoped_out_witnesses)

    def test_source_scope_is_invariant_under_numeric_renaming_and_new_prefix(self):
        for renamed in (False, True):
            transform = lambda text: tuple(10000 - x if renamed else x for x in encode(text, 'unicode'))
            memory = TrajectoryGenerationExperiment()
            for i, (query, target) in enumerate((
                ('Código de Daro?', 'Daro: 791.'),
                ('código de daro?', 'Daro: 791.'),
                ('código de daro?', 'Daro: 415.'),
            )):
                memory.observe(transform(query), observation_id=f'{i}:s', stream_id=str(i))
                memory.observe(transform(target), observation_id=f'{i}:t', stream_id=str(i))
            result = read(memory, transform('Lembre: Código de Daro?'))
            self.assertEqual(result.hypothesis, transform('Daro: 791.'))
            self.assertEqual(result.reason, 'SOURCE_SCOPED_ROOT_DESTINATION')
            self.assertEqual(len(result.scoped_out_witnesses), 1)
            self.assertIsNone(result.generation.selected)

    def test_full_destination_competition_is_not_hidden_by_a_known_root(self):
        memory = TrajectoryGenerationExperiment()
        for i, (query, target) in enumerate((((1, 2, 3, 4), (17, 18, 19)),
                                           ((1, 2, 3, 5), (90, 7, 8, 9, 91)),
                                           ((1, 2, 3, 6), (92, 7, 8, 9, 93)))):
            memory.observe(query, observation_id=f'{i}:s', stream_id=str(i))
            memory.observe(target, observation_id=f'{i}:t', stream_id=str(i))
        result = read(memory, (1, 2, 3, 4))
        self.assertEqual(result.generation.mode, 'COMBINED_RECALL')
        self.assertIsNone(result.hypothesis)
        self.assertFalse(result.scoped_out_witnesses)
        self.assertIn((17, 18, 19), {c.output for c in result.generation.candidates})
        self.assertIn((7, 8, 9), {c.output for c in result.generation.candidates})

    def test_root_consolidation_does_not_use_a_truncated_candidate_set(self):
        memory = TrajectoryGenerationExperiment()
        for i, query in enumerate(('Código de Daro?', 'código de daro?')):
            memory.observe(encode(query, 'unicode'), observation_id=f'{i}:s', stream_id=str(i))
            memory.observe(encode('Daro: 791.', 'unicode'), observation_id=f'{i}:t', stream_id=str(i))
        result = memory.contextual_route_hypothesis(encode('código de daro?', 'unicode'), beam_width=1)
        self.assertTrue(result.generation.truncated)
        self.assertIsNone(result.hypothesis)

    def test_all_existing_novel_carried_and_mixed_transfer_controls_survive(self):
        self.assertEqual(len(positive_controls()), 24)


    def test_unique_generic_fragment_is_withheld_without_erasing_it(self):
        memory = TrajectoryGenerationExperiment()
        memory.observe(encode('Código de Daro?', 'unicode'), observation_id='source')
        memory.observe(encode('Daro: 791.', 'unicode'), observation_id='target')
        query = encode('Temperatura de Marte?', 'unicode')
        baseline = memory.generate(query)
        self.assertEqual(baseline.mode, 'NODULE_RECALL')
        self.assertEqual(baseline.selected, encode('Daro', 'unicode'))
        result = read(memory, query)
        self.assertIsNone(result.hypothesis)
        self.assertEqual(result.reason, 'UNMATCHED_SHARED_SOURCE_CONTEXT')
        self.assertEqual(asdict(result.generation), asdict(baseline))
        self.assertTrue(result.shared_source_contexts)
        self.assertEqual(memory.generate(query).selected, baseline.selected)

    def test_case_change_is_absence_of_supported_context_not_a_normalized_answer(self):
        memory = TrajectoryGenerationExperiment()
        memory.observe(encode('Código de Daro?', 'unicode'), observation_id='source')
        memory.observe(encode('Daro: 791.', 'unicode'), observation_id='target')
        result = read(memory, encode('código de daro?', 'unicode'))
        self.assertIsNone(result.hypothesis)
        self.assertEqual(result.reason, 'UNMATCHED_SHARED_SOURCE_CONTEXT')

    def test_unique_supported_nodule_exposes_its_context_under_symbol_renaming(self):
        for rename in (False, True):
            transform = lambda xs: tuple(10000 - x if rename else x for x in xs)
            memory = TrajectoryGenerationExperiment()
            for i in range(2):
                memory.observe(transform((90+i, 7, 8, 9, 1, 2, 3, 100+i)),
                               observation_id=f'{i}:s', stream_id=str(i))
                memory.observe(transform((200+i, 7, 8, 9, 300+i)),
                               observation_id=f'{i}:t', stream_id=str(i))
            query = transform((1000,) * 16 + (1, 2, 3) + (1001,) * 16)
            result = read(memory, query)
            self.assertEqual(result.hypothesis, transform((7, 8, 9)))
            self.assertEqual(result.reason, 'SOURCE_CONTEXT_SUPPORTED_ROUTE')
            self.assertEqual(result.shared_source_contexts, (transform((1, 2, 3)),))


if __name__ == '__main__':
    unittest.main()
