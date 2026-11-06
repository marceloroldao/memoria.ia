from dataclasses import asdict
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from memoria_resolutiva.trajectory_generation_v2 import TrajectoryGenerationExperiment


def trained(carried=(False, False), target=(7, 8, 9), rename=False):
    memory = TrajectoryGenerationExperiment()
    transform = lambda xs: tuple(x * 101 + 17 if rename else x for x in xs)
    for i, same in enumerate(carried):
        source = (90 + 2*i,) + (target if same else ()) + (1, 2, 3, 91 + 2*i)
        destination = (94 + 2*i,) + target + (95 + 2*i,)
        memory.observe(transform(source), observation_id=f'{i}:source', stream_id=str(i))
        memory.observe(transform(destination), observation_id=f'{i}:target', stream_id=str(i))
    return memory, transform((100, 1, 2, 3, 101)), transform(target)


class TemporalNoduleContrastTests(unittest.TestCase):
    def test_new_in_pair_preserves_original_readout_and_cold_parity(self):
        memory, query, target = trained()
        before = memory.snapshot(), memory.learning_state()
        generated = asdict(memory.generate(query))
        contrast = memory.temporal_nodule_contrast(query)
        self.assertEqual(contrast.recall, memory.associated_nodules(query))
        self.assertEqual(contrast.candidates[0].symbols, target)
        self.assertEqual(contrast.candidates[0].introduced_pairs, 2)
        self.assertEqual(contrast.candidates[0].carried_pairs, 0)
        witness = contrast.candidates[0].witnesses[0]
        self.assertEqual(witness.source_spans, ())
        self.assertEqual(witness.target_spans, ((1, 4),))
        self.assertEqual(witness.query_source_spans, ())
        cold = TrajectoryGenerationExperiment.restore(memory.snapshot())
        self.assertEqual(asdict(contrast), asdict(cold.temporal_nodule_contrast(query)))
        self.assertEqual(asdict(memory.generate(query)), generated)
        self.assertEqual((memory.snapshot(), memory.learning_state()), before)

    def test_carried_target_is_still_a_valid_unique_recall(self):
        memory, query, target = trained((True, True))
        candidate = memory.temporal_nodule_contrast(query).candidates[0]
        self.assertEqual(candidate.introduced_pairs, 0)
        self.assertEqual(candidate.carried_pairs, 2)
        self.assertEqual(candidate.witnesses[0].source_spans, ((1, 4),))
        self.assertEqual(memory.generate(query).selected, target)

    def test_mixed_pairs_and_symbol_renaming_do_not_become_votes(self):
        memory, query, target = trained((True, False))
        candidate = memory.temporal_nodule_contrast(query).candidates[0]
        self.assertEqual((candidate.introduced_pairs, candidate.carried_pairs), (1, 1))
        before = asdict(memory.temporal_nodule_contrast(query))
        source = (90, *target, 1, 2, 3, 91)
        destination = (94, *target, 95)
        self.assertTrue(memory.observe(source, observation_id='0:source', stream_id='0').replayed)
        self.assertTrue(memory.observe(destination, observation_id='0:target', stream_id='0').replayed)
        self.assertEqual(asdict(memory.temporal_nodule_contrast(query)), before)
        renamed, renamed_query, _ = trained((True, False), rename=True)
        other = renamed.temporal_nodule_contrast(renamed_query).candidates[0]
        self.assertEqual((other.introduced_pairs, other.carried_pairs), (1, 1))
        self.assertEqual(sorted(w.source_spans for w in other.witnesses),
                         sorted(w.source_spans for w in candidate.witnesses))

    def test_repeated_target_positions_and_full_query_are_exact(self):
        memory, query, target = trained((True, True), target=(7, 7, 8))
        carried = memory.temporal_nodule_contrast(query).candidates[0]
        self.assertEqual(carried.witnesses[0].source_spans, ((1, 4),))
        self.assertEqual(carried.witnesses[0].target_spans, ((1, 4),))
        memory, _, target = trained(target=(7, 7, 8))
        source = (90, 1, 2, 3, 91)
        candidate = next(c for c in memory.temporal_nodule_contrast(source).candidates
                         if c.symbols == target)
        matching = [w for w in candidate.witnesses if w.query_source_spans]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].query_source_spans, ((0, len(source)),))
        self.assertEqual(matching[0].source_spans, ())

    def test_overlapping_spans_are_not_collapsed(self):
        memory = TrajectoryGenerationExperiment()
        for i in range(2):
            memory.observe((90 + 2*i, 7, 7, 7, 1, 2, 3, 91 + 2*i),
                           observation_id=f'{i}:s', stream_id=str(i))
            memory.observe((94 + 2*i, 7, 7, 95 + 2*i),
                           observation_id=f'{i}:t', stream_id=str(i))
        candidate = next(c for c in memory.temporal_nodule_contrast((100, 1, 2, 3, 101)).candidates
                         if c.symbols == (7, 7))
        self.assertEqual(candidate.witnesses[0].source_spans, ((1, 3), (2, 4)))
        self.assertEqual(candidate.witnesses[0].target_spans, ((1, 3),))

    def test_competition_limits_and_hierarchy_isolation_remain_visible(self):
        memory, query, _ = trained()
        memory.observe((110, 1, 2, 3, 111), observation_id='extra:s', stream_id='extra')
        memory.observe((120, 17, 18, 19, 121), observation_id='extra:t', stream_id='extra')
        memory.observe((112, 1, 2, 3, 113), observation_id='extra2:s', stream_id='extra2')
        memory.observe((122, 17, 18, 19, 123), observation_id='extra2:t', stream_id='extra2')
        result = memory.temporal_nodule_contrast(query, limit=1)
        self.assertTrue(result.recall.truncated)
        self.assertTrue(result.recall.ambiguous)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(memory.temporal_nodule_contrast(query, hierarchy_id='other').candidates, ())
        with self.assertRaises(ValueError):
            memory.temporal_nodule_contrast(query, limit=0)


if __name__ == '__main__':
    unittest.main()
