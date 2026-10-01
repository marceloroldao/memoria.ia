from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import trajectory_contextual_hypothesis_probe as contextual
from trajectory_transported_scope_probe import TransportedScopeExperiment, checked_read
from trajectory_native_bridge_probe import adapt, fixtures
from trajectory_response_quality_probe import TrajectoryGenerationExperiment, encode


class TransportedScopeTests(unittest.TestCase):
    def test_ordered_pairs_recover_with_raw_adapters_and_bijective_renaming(self):
        for adapter in ('unicode', 'utf8'):
            for renamed in (False, True):
                transform = lambda text: tuple(10000 - x if renamed else x for x in encode(text, adapter))
                memory = TrajectoryGenerationExperiment()
                for i, (query, answer) in enumerate((('Qual nome do meu drone?', 'Meu drone se chama Auri.'),
                                                     ('Qual nome do meu robô?', 'Meu robô se chama Lumo.'))):
                    memory.observe(transform(query), observation_id=f'{i}:q', stream_id=str(i))
                    memory.observe(transform(answer), observation_id=f'{i}:a', stream_id=str(i))
                for prefix in ('', 'Lembre: '):
                    result = checked_read(memory, transform(prefix + 'Qual nome do meu drone?'))
                    self.assertEqual(result.hypothesis, transform('Meu drone se chama Auri.'))
                    self.assertEqual(result.reason, 'TRANSPORTED_SOURCE_SCOPE')
                    self.assertIsNone(result.generation.selected)
                    self.assertIn(transform('eu robô'), {c.output for c in result.generation.candidates})
                    self.assertTrue(result.scoped_out_witnesses)

    def test_unsupported_origin_stays_blocked_even_with_a_third_discriminator(self):
        for extra in (False, True):
            memory = TrajectoryGenerationExperiment()
            pairs = [('Código de Daro?', 'Daro: 791.'), ('código de daro?', 'Daro: 415.')]
            if extra:
                pairs.append(('Código de Rumo?', 'Rumo: 827.'))
            for i, (query, answer) in enumerate(pairs):
                memory.observe(encode(query, 'unicode'), observation_id=f'{i}:q', stream_id=str(i))
                memory.observe(encode(answer, 'unicode'), observation_id=f'{i}:a', stream_id=str(i))
            result = checked_read(memory, encode('Código de Daro?', 'unicode'))
            self.assertIsNone(result.hypothesis)
            self.assertFalse(result.scoped_out_witnesses)

    def test_discriminator_in_query_does_not_remove_competition(self):
        memory, _ = adapt(bridge_pairs(), 'unicode')
        result = checked_read(memory, encode('eu robô: Qual nome do meu drone?', 'unicode'))
        self.assertIsNone(result.hypothesis)

    def test_truncation_stays_blocked(self):
        memory, _ = adapt(bridge_pairs(), 'unicode')
        result = checked_read(memory, encode('Qual nome do meu drone?', 'unicode'), beam_width=1)
        self.assertTrue(result.generation.truncated)
        self.assertIsNone(result.hypothesis)

    def test_complete_carried_destination_cannot_be_discarded(self):
        memory = TrajectoryGenerationExperiment()
        for i, (query, answer) in enumerate((((1, 2, 3, 4), (17, 18, 19)),
                                            ((1, 2, 3, 5, 7, 8, 9), (7, 8, 9)))):
            memory.observe(query, observation_id=f'{i}:q', stream_id=str(i))
            memory.observe(answer, observation_id=f'{i}:a', stream_id=str(i))
        result = checked_read(memory, (1, 2, 3, 4))
        self.assertEqual(result.generation.mode, 'COMBINED_RECALL')
        self.assertIn((7, 8, 9), {c.output for c in result.generation.candidates})
        self.assertIsNone(result.hypothesis)

    def test_all_eighteen_existing_contracts_with_option_enabled(self):
        import test_contextual_route_hypothesis as existing
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(existing.ContextualRouteHypothesisTests)
        result = unittest.TestResult()
        with patch.object(existing, 'TrajectoryGenerationExperiment', TransportedScopeExperiment), \
             patch.object(contextual, 'TrajectoryGenerationExperiment', TransportedScopeExperiment):
            suite.run(result)
        self.assertEqual(result.testsRun, 18)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])


def bridge_pairs():
    return next(rows for stage, rows in fixtures() if stage == 'ordered_pairs')
