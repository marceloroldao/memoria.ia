from __future__ import annotations

import copy
from math import exp
from pathlib import Path
import tempfile
import unittest

from memoria_resolutiva.structural_state_persistence import ContentAddressedStatePersistence
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex
from memoria_resolutiva.trajectory_generation_v2 import GenerationConfig, TrajectoryGenerationExperiment


def text_symbols(text):
    # Adapter only. The engine has no tokenizer or vocabulary.
    return tuple(map(ord, text))


class TrajectoryGenerationTests(unittest.TestCase):
    def test_known_occurrence_updates_warm_projection_without_rebuild_or_reprojection(self):
        from dataclasses import asdict
        from unittest.mock import patch

        memory = TrajectoryGenerationExperiment()
        cue, target = (10, 1, 2, 3, 11), (20, 7, 8, 9, 21)
        for i, root in enumerate((cue, target, (30, 1, 2, 3, 31), (40, 7, 8, 9, 41))):
            memory.observe(root, observation_id=f"root:{i}", stream_id=f"archive:{i}")
        query = (50, 1, 2, 3, 51)
        self.assertEqual(memory.associated_nodules(query).candidates, ())
        view = memory._compositional_views["default"]
        with patch.object(view, "_project", wraps=view._project) as project:
            memory.observe(cue, observation_id="active:cue", stream_id="active")
            receipt = memory.observe(target, observation_id="active:target", stream_id="active")
            result = memory.associated_nodules(query)
            self.assertEqual(result.selected, (7, 8, 9))
            self.assertFalse(receipt.learned)
            self.assertIs(memory._compositional_views["default"], view)
            self.assertEqual(project.call_count, 0)
        cold = TrajectoryGenerationExperiment.restore(memory.snapshot())
        self.assertEqual(asdict(result), asdict(cold.associated_nodules(query)))

    def test_incremental_view_rejects_unknown_or_changed_content_before_mutation(self):
        from dataclasses import asdict
        from memoria_resolutiva.compositional_association_v2 import CompositionObservation

        memory = TrajectoryGenerationExperiment()
        receipt = memory.observe((1, 2, 3), observation_id="one")
        memory.observe((1, 2, 4), observation_id="two")
        query = (90, 1, 2, 91)
        before = asdict(memory.associated_nodules(query)), memory.snapshot()
        view = memory._compositional_views["default"]
        for event in (CompositionObservation("unknown", "stream", (1, 2, 3)),
                      CompositionObservation(receipt.payload_id, "stream", (3, 2, 1))):
            with self.assertRaises(ValueError):
                view.append_known_occurrence(event)
            self.assertEqual((asdict(memory.associated_nodules(query)), memory.snapshot()), before)

    def test_bounded_incremental_history_keeps_absolute_occurrence_ticks(self):
        from dataclasses import asdict

        memory = TrajectoryGenerationExperiment(GenerationConfig(
            temporal_decay=1.0, forgetting_rate=0.01, trace_floor=0.01))
        roots = ((10, 1, 2, 3, 11), (20, 7, 8, 9, 21), (30, 4, 5, 6, 31),
                 (40, 1, 2, 3, 41), (50, 7, 8, 9, 51), (60, 4, 5, 6, 61))
        for index, root in enumerate(roots):
            memory.observe(root, observation_id=f"root:{index}", stream_id=f"archive:{index}")
        query = (90, 1, 2, 3, 91)
        memory.associated_nodules(query)
        for index in range(30):
            memory.observe(roots[index % 3], observation_id=f"repeat:{index}", stream_id="active")
        view = memory._compositional_views["default"]
        for depth, streams in view._histories.items():
            self.assertLessEqual(len(streams["active"]), view._fields[depth].temporal_horizon)
            self.assertEqual(view._ticks[(depth, "active")], 30)
        cold = TrajectoryGenerationExperiment.restore(memory.snapshot())
        self.assertEqual(asdict(memory.trace_nodule_paths(query)), asdict(cold.trace_nodule_paths(query)))
        self.assertEqual(asdict(memory.associated_nodules(query)), asdict(cold.associated_nodules(query)))

    def test_composition_catalogue_reused_until_unique_content_changes(self):
        from unittest.mock import patch

        memory = TrajectoryGenerationExperiment()
        memory.observe((1, 2, 3, 4), observation_id="one")
        memory.observe((1, 2, 6, 7), observation_id="two")
        with patch.object(memory._hierarchy, "build", wraps=memory._hierarchy.build) as build:
            before = memory.levels()
            memory.observe((1, 2, 3, 4), observation_id="copy")
            memory.associated_nodules((90, 1, 2, 91))
            memory.generate((90, 1, 2, 91))
            self.assertEqual(memory.levels(), before)
            self.assertEqual(build.call_count, 1)
            memory.observe((8, 6, 7, 9), observation_id="new-context")
            after = memory.levels()
            self.assertNotEqual(after, before)
            self.assertEqual(after, TrajectoryGenerationExperiment.restore(memory.snapshot()).levels())
            self.assertEqual(build.call_count, 2)
            memory.observe((1, 2, 3, 4), observation_id="other", hierarchy_id="other")
            self.assertEqual(memory.levels(), after)
            self.assertEqual(build.call_count, 2)
            self.assertEqual(memory.levels(hierarchy_id="other"), ())
            self.assertEqual(memory.levels(), after)
            self.assertEqual(build.call_count, 4)

    def test_read_projection_reuse_matches_cold_reconstruction(self):
        from unittest.mock import patch
        from memoria_resolutiva.compositional_association_v2 import CompositionalAssociationView

        memory = TrajectoryGenerationExperiment()
        for index, payload in enumerate(((90, 1, 2, 3, 91), (92, 7, 8, 9, 93),
                                          (94, 1, 2, 3, 95), (96, 7, 8, 9, 97))):
            memory.observe(payload, observation_id=str(index))
        query = (100, 1, 2, 3, 101)
        state, learned = memory.snapshot(), memory.learning_state()
        cold = TrajectoryGenerationExperiment.restore(state)
        expected = (cold.associated_nodules(query), cold.route_stability(query),
                    cold.trace_nodule_paths(query), cold.generate(query))
        with patch("memoria_resolutiva.trajectory_generation_v2.CompositionalAssociationView",
                   wraps=CompositionalAssociationView) as rebuild:
            for _ in range(3):
                actual = (memory.associated_nodules(query), memory.route_stability(query),
                          memory.trace_nodule_paths(query), memory.generate(query))
                self.assertEqual(actual, expected)
            self.assertEqual(rebuild.call_count, 1)
        self.assertEqual((memory.snapshot(), memory.learning_state()), (state, learned))

    def test_cached_projection_updates_for_reused_target_and_forgetting(self):
        memory = TrajectoryGenerationExperiment(GenerationConfig(forgetting_rate=0.05))
        cue, target = (1, 2, 3), (7, 8, 9)
        root = (20, *target, 21)
        for index, payload in enumerate(((10, *cue, 11), root, (30, *cue, 31),
                                          (40, *target, 41))):
            memory.observe(payload, observation_id=f"known:{index}", stream_id=f"old:{index}")
        query = (90, *cue, 91)
        self.assertEqual(memory.associated_nodules(query).candidates, ())
        memory.observe((50, *cue, 51), observation_id="new:cue", stream_id="new")
        self.assertEqual(memory.associated_nodules(query).candidates, ())
        receipt = memory.observe(root, observation_id="new:target", stream_id="new")
        self.assertFalse(receipt.learned)
        recalled = memory.associated_nodules(query)
        self.assertEqual(recalled.selected, target)
        self.assertEqual(recalled, TrajectoryGenerationExperiment.restore(
            memory.snapshot()).associated_nodules(query))
        # Even an occurrence with no new content/pair advances the forgetting clock.
        memory.observe(root, observation_id="new:copy", stream_id="new")
        decayed = memory.associated_nodules(query)
        self.assertLess(decayed.candidates[0].weight, recalled.candidates[0].weight)
        self.assertEqual(decayed, TrajectoryGenerationExperiment.restore(
            memory.snapshot()).associated_nodules(query))

    def test_projection_replay_rejection_and_other_hierarchy_preserve_warm_view(self):
        from unittest.mock import patch
        from memoria_resolutiva.compositional_association_v2 import CompositionalAssociationView

        memory = TrajectoryGenerationExperiment()
        memory.observe((1, 2, 3), observation_id="first", hierarchy_id="one")
        memory.observe((7, 8, 9), observation_id="second", hierarchy_id="one")
        with patch("memoria_resolutiva.trajectory_generation_v2.CompositionalAssociationView",
                   wraps=CompositionalAssociationView) as rebuild:
            original = memory.associated_nodules((1, 2, 3), hierarchy_id="one")
            memory.observe((1, 2, 3), observation_id="first", hierarchy_id="one")
            with self.assertRaises(ValueError):
                memory.observe((3, 2, 1), observation_id="first", hierarchy_id="one")
            memory.observe((4, 5, 6), observation_id="other", hierarchy_id="two")
            self.assertEqual(memory.associated_nodules((1, 2, 3), hierarchy_id="one"), original)
            self.assertEqual(rebuild.call_count, 1)

    def test_empty_memory_echoes_without_learning_output(self):
        memory = TrajectoryGenerationExperiment()
        for i, text in enumerate(("oi", "hoje o dia está bonito", "hoje está quente")):
            result, receipt = memory.respond(text_symbols(text), observation_id=str(i))
            self.assertEqual(result.mode, "ECHO")
            self.assertEqual(result.selected, text_symbols(text))
            self.assertTrue(receipt.learned)
        self.assertEqual(memory.learning_state()["learned_payloads"], 3)
        self.assertEqual(len(memory.snapshot()["observations"]), 3)

    def test_payload_reuse_and_replay_have_zero_learning_effect(self):
        memory = TrajectoryGenerationExperiment()
        first = memory.observe((1, 1, 2, 3), observation_id="first")
        before = memory.learning_state()
        for i in range(30):
            receipt = memory.observe((1, 1, 2, 3), observation_id=f"copy:{i}", stream_id=f"stream:{i}")
            self.assertEqual(receipt.payload_id, first.payload_id)
            self.assertFalse(receipt.learned)
        self.assertEqual(memory.learning_state(), before)
        self.assertEqual(len(memory.snapshot()["nodes"]), 1)
        snapshot = memory.snapshot()
        self.assertTrue(memory.observe((1, 1, 2, 3), observation_id="first").replayed)
        self.assertEqual(memory.snapshot(), snapshot)

    def test_new_context_reuses_nodule_and_adds_evidence(self):
        memory = TrajectoryGenerationExperiment()
        first = memory.observe((1, 1, 2, 3), observation_id="first")
        before = memory.association(2, 3)
        second = memory.observe((9, 8, 1, 1, 2, 3), observation_id="second")
        self.assertTrue(second.learned)
        self.assertEqual(memory.snapshot()["nodes"][1]["children"], [9, 8, first.payload_id])
        self.assertEqual(memory.expand(second.payload_id), (9, 8, 1, 1, 2, 3))
        self.assertGreater(memory.association(2, 3), before)
        self.assertEqual(memory.learning_state()["learned_payloads"], 2)
        self.assertTrue(memory.levels())

    def test_repeated_target_can_form_new_ordered_relation_without_payload_vote(self):
        memory = TrajectoryGenerationExperiment()
        source, target, later = (1, 2, 3), (7, 8, 9), (4, 5, 6)
        memory.observe(target, observation_id="known", stream_id="archive")
        memory.observe(source, observation_id="new-context", stream_id="live")
        content_count = memory.learning_state()["learned_payloads"]
        duplicate = memory.observe(target, observation_id="reused-target", stream_id="live")
        self.assertFalse(duplicate.learned)
        self.assertEqual(duplicate.new_relations, 1)
        self.assertEqual(memory.learning_state()["learned_payloads"], content_count)
        self.assertEqual(len(memory.snapshot()["nodes"]), content_count)
        self.assertEqual([neighbor.symbols for neighbor in memory.temporal_neighbors(source)],
                         [target])
        self.assertEqual(memory.temporal_neighbors(source)[0].streams, ("live",))
        query = (90, *source, 91)
        self.assertEqual(memory.generate(query).selected, target)
        first_weight = memory.temporal_neighbors(source)[0].weight
        before = memory.learning_state()
        memory.observe(source, observation_id="repeat-source", stream_id="other")
        same_pair = memory.observe(target, observation_id="repeat-target", stream_id="other")
        self.assertEqual(same_pair.new_relations, 0)
        self.assertEqual(memory.learning_state(), before)
        self.assertEqual(memory.temporal_neighbors(source)[0].weight, first_weight)

        memory.observe(later, observation_id="later", stream_id="live")
        neighbors = {item.symbols: item for item in memory.temporal_neighbors(source)}
        self.assertAlmostEqual(neighbors[target].weight, 1.0)
        self.assertAlmostEqual(neighbors[later].weight, exp(-0.35))
        saved = memory.snapshot()
        self.assertEqual(TrajectoryGenerationExperiment.restore(saved).generate(query),
                         memory.generate(query))
        self.assertEqual(TrajectoryGenerationExperiment.restore(saved).learning_state(),
                         memory.learning_state())

        reverse = TrajectoryGenerationExperiment()
        reverse.observe(target, observation_id="known", stream_id="archive")
        reverse.observe(target, observation_id="copy", stream_id="live")
        reverse.observe(source, observation_id="source", stream_id="live")
        self.assertEqual(reverse.temporal_neighbors(source), ())

    def test_same_kernel_forms_multiple_scales_and_preserves_every_position(self):
        memory = TrajectoryGenerationExperiment()
        core = (1, 1, 2, 3, 4, 5, 6, 7, 8)
        memory.observe(core + (90,), observation_id="a")
        memory.observe(core + (91,), observation_id="b")
        levels = memory.levels()
        self.assertGreaterEqual(len(levels), 2)
        for scale in range(len(levels) + 1):
            result = memory.generate(core, scale=scale)
            self.assertEqual({c.output for c in result.candidates}, {core + (90,), core + (91,)})
            self.assertTrue(result.ambiguous)
            self.assertFalse(result.truncated)
        self.assertGreater(memory.generate(core).scale, 0)

    def test_novel_context_completes_from_learned_suffix(self):
        memory = TrajectoryGenerationExperiment()
        stored = text_symbols("hoje o dia está bonito")
        memory.observe(stored, observation_id="a")
        query = text_symbols("amanhã o dia está ")
        before = memory.snapshot()
        fields = memory.learning_state()
        result = memory.generate(query)
        self.assertEqual(result.mode, "CONTINUATION")
        self.assertEqual(result.selected, text_symbols("amanhã o dia está bonito"))
        self.assertNotEqual(result.selected, stored)
        self.assertTrue(all(step.supporting_payloads for step in result.candidates[0].steps))
        self.assertEqual(memory.snapshot(), before)
        self.assertEqual(memory.learning_state(), fields)

    def test_competing_routes_are_exposed_and_distinct_contexts_change_support(self):
        memory = TrajectoryGenerationExperiment()
        memory.observe((1, 2, 3), observation_id="a")
        memory.observe((1, 2, 4), observation_id="b")
        result = memory.generate((1, 2))
        self.assertIsNone(result.selected)
        self.assertTrue(result.ambiguous)
        self.assertEqual({c.continuation for c in result.candidates}, {(3,), (4,)})
        self.assertEqual({c.steps[0].relative_support for c in result.candidates}, {0.5})
        memory.observe((9, 1, 2, 4), observation_id="new-context")
        weighted = memory.generate((1, 2))
        supports = {c.continuation: c.steps[0].relative_support for c in weighted.candidates}
        self.assertAlmostEqual(supports[(4,)], 2 / 3)
        self.assertAlmostEqual(supports[(3,)], 1 / 3)
        self.assertTrue(weighted.ambiguous)  # Stronger support is not proof.
        before = weighted
        memory.observe((9, 1, 2, 4), observation_id="copy")
        self.assertEqual(memory.generate((1, 2)), before)

    def test_each_payload_supplies_at_most_one_vote_per_next_address(self):
        memory = TrajectoryGenerationExperiment()
        memory.observe((1, 2, 3, 1, 2, 3), observation_id="a")
        memory.observe((1, 2, 4), observation_id="b")
        result = memory.generate((1, 2), max_steps=1, scale=0)
        self.assertEqual({c.steps[0].relative_support for c in result.candidates}, {0.5})

    def test_sequential_proximity_learns_root_relations_without_reply_links(self):
        memory = TrajectoryGenerationExperiment()
        for i, payload in enumerate(((1, 2), (7, 8), (9, 10))):
            memory.observe(payload, observation_id=str(i))
        neighbors = memory.temporal_neighbors((1, 2))
        self.assertEqual([n.symbols for n in neighbors], [(7, 8), (9, 10)])
        self.assertAlmostEqual(neighbors[0].weight, 1.0)
        self.assertAlmostEqual(neighbors[1].weight, exp(-0.35))
        result = memory.generate((1, 2))
        self.assertEqual(result.mode, "TEMPORAL_RECALL")
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.selected)
        self.assertEqual({c.output for c in result.candidates}, {(7, 8), (9, 10)})

    def test_proximity_changes_with_order_and_respects_capture_boundaries(self):
        forward, reverse, separate = (TrajectoryGenerationExperiment() for _ in range(3))
        forward.observe((1, 2), observation_id="a")
        forward.observe((7, 8), observation_id="b")
        reverse.observe((7, 8), observation_id="b")
        reverse.observe((1, 2), observation_id="a")
        separate.observe((1, 2), observation_id="a", stream_id="one")
        separate.observe((7, 8), observation_id="b", stream_id="two")
        self.assertEqual(forward.generate((1, 2)).selected, (7, 8))
        self.assertEqual(reverse.generate((1, 2)).mode, "ECHO")
        self.assertEqual(separate.temporal_neighbors((1, 2)), ())
        self.assertGreater(forward.association(1, 7, channel="temporal"), 0)
        self.assertEqual(separate.association(1, 7, channel="temporal"), 0)

    def test_hierarchies_are_isolated_but_share_content_storage(self):
        memory = TrajectoryGenerationExperiment()
        memory.observe((1, 2, 3), observation_id="a", hierarchy_id="one")
        before = memory.learning_state()
        self.assertEqual(memory.generate((1, 2), hierarchy_id="two").mode, "ECHO")
        self.assertEqual(memory.learning_state(), before)
        receipt = memory.observe((1, 2, 3), observation_id="b", hierarchy_id="two")
        self.assertTrue(receipt.learned)
        self.assertEqual(len(memory.snapshot()["nodes"]), 1)
        self.assertEqual(memory.generate((1, 2), hierarchy_id="two").selected, (1, 2, 3))

    def test_end_of_observation_competes_with_continuation(self):
        memory = TrajectoryGenerationExperiment()
        memory.observe((1, 2), observation_id="a", stream_id="one")
        memory.observe((1, 2, 3), observation_id="b", stream_id="two")
        result = memory.generate((1, 2))
        self.assertEqual({c.output for c in result.candidates}, {(1, 2), (1, 2, 3)})
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.selected)

    def test_matching_continuation_and_temporal_target_are_not_two_votes(self):
        memory = TrajectoryGenerationExperiment()
        memory.observe((1, 2), observation_id="cue", stream_id="episode")
        memory.observe((1, 2, 3), observation_id="target", stream_id="episode")
        result = memory.generate((1, 2))
        self.assertEqual(result.mode, "COMBINED_ROUTES")
        self.assertEqual([candidate.output for candidate in result.candidates],
                         [(1, 2, 3), (1, 2)])
        self.assertEqual(result.temporal_evidence[0].symbols, (1, 2, 3))
        self.assertEqual(result.candidates[0].continuation, (3,))
        self.assertTrue(result.ambiguous)  # The observed end still competes.
        self.assertIsNone(result.selected)

    def test_pruned_continuation_does_not_erase_independent_root_recall(self):
        memory = TrajectoryGenerationExperiment()
        query, target = (1, 2, 3, 4, 5), (7, 8, 9)
        memory.observe(query, observation_id="cue", stream_id="episode")
        memory.observe(target, observation_id="target", stream_id="episode")
        memory.observe((80, *query, 6), observation_id="extension", stream_id="other")
        for index in range(3):
            memory.observe((90 + index, *query), observation_id=f"end:{index}",
                           stream_id=f"end:{index}")

        full = memory.generate(query)
        self.assertEqual(full.mode, "COMBINED_ROUTES")
        self.assertEqual({candidate.output for candidate in full.candidates},
                         {query, (*query, 6), target})
        stored = memory.snapshot(), memory.learning_state()
        narrow = memory.generate(query, beam_width=1)
        self.assertEqual(narrow.mode, "COMBINED_ROUTES")
        self.assertEqual([candidate.output for candidate in narrow.candidates], [query])
        self.assertEqual(narrow.temporal_evidence[0].symbols, target)
        self.assertEqual(narrow.temporal_evidence[0].streams, ("episode",))
        self.assertTrue(narrow.ambiguous)
        self.assertTrue(narrow.truncated)
        self.assertIsNone(narrow.selected)
        self.assertEqual((memory.snapshot(), memory.learning_state()), stored)
        self.assertEqual(TrajectoryGenerationExperiment.restore(
            stored[0]).generate(query, beam_width=1), narrow)

        memory.observe(query, observation_id="copy", stream_id="replay")
        self.assertEqual(memory.learning_state(), stored[1])
        self.assertEqual(memory.generate(query, beam_width=1), narrow)

    def test_beam_pruning_and_cycles_are_explicit_and_bounded(self):
        memory = TrajectoryGenerationExperiment(GenerationConfig(max_context=2))
        memory.observe((1, 2, 1, 2, 3), observation_id="a")
        before = memory.learning_state()
        result = memory.generate((1, 2), scale=0, max_steps=5, beam_width=3)
        self.assertTrue(result.truncated)
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.selected)
        self.assertLessEqual(len(result.candidates), 3)
        self.assertTrue(all(len(c.continuation) <= 5 for c in result.candidates))
        pruned = memory.generate((1, 2), scale=0, max_steps=8, beam_width=1)
        self.assertTrue(pruned.truncated)
        self.assertIsNone(pruned.selected)
        self.assertEqual(memory.learning_state(), before)

    def test_opaque_symbol_renaming_preserves_routes_and_support(self):
        payloads = [(1, 1, 2, 3, 4, 5, 6, 7, 8, 90), (1, 1, 2, 3, 4, 5, 6, 7, 8, 91)]
        mapping = {symbol: 10000 - symbol * 7 for payload in payloads for symbol in payload}
        original, renamed = TrajectoryGenerationExperiment(), TrajectoryGenerationExperiment()
        for i, payload in enumerate(payloads):
            original.observe(payload, observation_id=str(i))
            renamed.observe(tuple(mapping[s] for s in payload), observation_id=str(i))
        query = tuple(payloads[0][:-1])
        left = original.generate(query)
        right = renamed.generate(tuple(mapping[s] for s in query))
        expected = {(tuple(mapping[s] for s in c.output), c.log_score) for c in left.candidates}
        self.assertEqual(expected, {(c.output, c.log_score) for c in right.candidates})
        self.assertEqual((left.mode, left.ambiguous, left.scale), (right.mode, right.ambiguous, right.scale))

    def test_respond_never_stores_its_generated_continuation(self):
        memory = TrajectoryGenerationExperiment()
        memory.observe((1, 2, 3), observation_id="a")
        result, receipt = memory.respond((9, 1, 2), observation_id="b")
        self.assertEqual(result.selected, (9, 1, 2, 3))
        self.assertEqual(memory.expand(receipt.payload_id), (9, 1, 2))
        self.assertEqual({memory.expand(n["address"]) for n in memory.snapshot()["nodes"]},
                         {(1, 2, 3), (9, 1, 2)})

    def test_recombination_across_observations_is_a_witnessed_hypothesis(self):
        memory = TrajectoryGenerationExperiment(GenerationConfig(max_context=2))
        a = memory.observe((1, 2, 3, 4), observation_id="a")
        b = memory.observe((3, 4, 5, 6), observation_id="b")
        result = memory.generate((9, 1, 2), scale=0)
        self.assertEqual({c.output for c in result.candidates},
                         {(9, 1, 2, 3, 4), (9, 1, 2, 3, 4, 5, 6)})
        longer = next(c for c in result.candidates if len(c.output) == 7)
        witnesses = {root for step in longer.steps for root in step.supporting_payloads}
        self.assertEqual(witnesses, {a.payload_id, b.payload_id})
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.selected)

    def test_unrelated_and_reversed_contexts_do_not_invent_routes(self):
        memory = TrajectoryGenerationExperiment()
        memory.observe((1, 2, 3, 4), observation_id="a")
        for query in ((91, 92), (2, 1), (4, 3)):
            self.assertEqual(memory.generate(query).mode, "ECHO")
            self.assertEqual(memory.generate(query).selected, query)

    def test_query_inside_larger_composition_keeps_all_competing_routes(self):
        memory = TrajectoryGenerationExperiment()
        for i, payload in enumerate(((1, 2, 3), (1, 2, 4), (9, 1, 2, 4))):
            memory.observe(payload, observation_id=str(i))
        for scale in range(len(memory.levels()) + 1):
            result = memory.generate((1, 2), scale=scale)
            self.assertEqual({c.continuation for c in result.candidates}, {(3,), (4,)})
            support = {c.continuation: c.steps[0].relative_support for c in result.candidates}
            self.assertAlmostEqual(support[(4,)], 2 / 3)

    def test_binary_and_unicode_roundtrip_without_normalization(self):
        memory = TrajectoryGenerationExperiment()
        binary = bytes([0, 255, 255, 0, 1, 1, 128])
        a = memory.observe(binary, observation_id="binary", hierarchy_id="bytes")
        text = "ação  café\n cafe\u0301"
        b = memory.observe(text_symbols(text), observation_id="text", hierarchy_id="codepoints")
        restored = TrajectoryGenerationExperiment.restore(memory.snapshot())
        self.assertEqual(bytes(restored.expand(a.payload_id)), binary)
        self.assertEqual("".join(map(chr, restored.expand(b.payload_id))), text)

    def test_reopen_restores_weights_compounds_and_continuations(self):
        memory = TrajectoryGenerationExperiment()
        for i, payload in enumerate(((1, 1, 2, 3), (9, 1, 1, 2, 3), (1, 1, 2, 4), (1, 1, 2, 4))):
            memory.observe(payload, observation_id=str(i))
        with tempfile.TemporaryDirectory() as directory:
            persistence = ContentAddressedStatePersistence(
                Path(directory), namespace="trajectory-generation-test", backend="sqlite", allow_fallback=False,
            )
            receipt = memory.save(persistence)
            self.assertEqual(receipt, memory.save(persistence))
            reopened = TrajectoryGenerationExperiment.load(persistence, receipt)
        self.assertEqual(reopened.snapshot(), memory.snapshot())
        self.assertEqual(reopened.learning_state(), memory.learning_state())
        self.assertEqual(reopened.levels(), memory.levels())
        self.assertEqual(reopened.generate((1, 1, 2)), memory.generate((1, 1, 2)))
        self.assertEqual(reopened.temporal_neighbors((1, 1, 2, 3)), memory.temporal_neighbors((1, 1, 2, 3)))

    def test_invalid_inputs_and_reused_identity_leave_memory_unchanged(self):
        memory = TrajectoryGenerationExperiment()
        memory.observe((1, 1, 2), observation_id="same")
        before = memory.snapshot(), memory.learning_state()
        for payload in ((), (-1,), (True,), (1.5,), ("1",)):
            with self.assertRaises(ValueError):
                memory.observe(payload, observation_id="invalid")
        with self.assertRaises(ValueError):
            memory.observe((1, 2), observation_id="same")
        with self.assertRaises(ValueError):
            memory.observe((1, 1, 2), observation_id="same", stream_id="different")
        self.assertEqual((memory.snapshot(), memory.learning_state()), before)
        for options in ({"min_context": 5, "max_context": 4}, {"temporal_decay": float("nan")},
                        {"forgetting_rate": -1}, {"max_depth": True}):
            with self.assertRaises(ValueError):
                GenerationConfig(**options)

    def test_corrupted_or_cyclic_snapshot_is_rejected(self):
        memory = TrajectoryGenerationExperiment()
        memory.observe((1, 2, 3), observation_id="a")
        corrupt = copy.deepcopy(memory.snapshot())
        corrupt["nodes"][0]["children"][0] = 99
        with self.assertRaises(ValueError):
            TrajectoryGenerationExperiment.restore(corrupt)
        cyclic = copy.deepcopy(memory.snapshot())
        cyclic["nodes"][0]["children"] = [cyclic["nodes"][0]["address"]]
        with self.assertRaises(ValueError):
            TrajectoryGenerationExperiment.restore(cyclic)

    def test_lossless_index_is_opt_in_and_queries_keep_positions(self):
        legacy, lossless = StructuralTrajectoryIndex(), StructuralTrajectoryIndex(preserve_repetitions=True)
        for index in (legacy, lossless):
            index.ingest_addresses((1, 1, 2), hierarchy_id="h", source_id="a", sequence=0)
        self.assertEqual(legacy.snapshot()[0].addresses, (1, 2))
        self.assertEqual(lossless.snapshot()[0].addresses, (1, 1, 2))
        self.assertEqual(lossless.frontier((1, 1), hierarchy_id="h").resolved_address, 2)
        self.assertEqual(lossless.resolve_addresses((1, 1, 2), hierarchy_id="h")[0].ordered_overlap, 3)
        restored = StructuralTrajectoryIndex.restore(lossless.snapshot(), preserve_repetitions=True)
        self.assertEqual(restored.snapshot(), lossless.snapshot())
        with self.assertRaises(ValueError):
            StructuralTrajectoryIndex.restore(lossless.snapshot())

    def test_intermediate_nodule_recall_emerges_without_manual_links(self):
        memory = TrajectoryGenerationExperiment()
        a = memory.observe((90, 1, 2, 3, 91), observation_id="a")
        c = memory.observe((94, 7, 8, 9, 95), observation_id="c")
        self.assertEqual(memory.associated_nodules((100, 1, 2, 3, 101)).candidates, ())
        b = memory.observe((92, 1, 2, 3, 93), observation_id="b")
        d = memory.observe((96, 7, 8, 9, 97), observation_id="d")
        before = memory.snapshot(), memory.learning_state()

        result = memory.associated_nodules((100, 1, 2, 3, 101))
        self.assertEqual(result.depth, 1)
        self.assertEqual(result.selected, (7, 8, 9))
        self.assertEqual({node.symbols for node in result.candidates}, {(7, 8, 9)})
        self.assertAlmostEqual(result.candidates[0].weight, (2 + exp(-0.7)) / 9)
        self.assertEqual(
            set(result.candidates[0].witnesses),
            {(a.payload_id, c.payload_id, "default"),
             (a.payload_id, d.payload_id, "default"),
             (b.payload_id, d.payload_id, "default")},
        )
        generated = memory.generate((100, 1, 2, 3, 101))
        self.assertEqual(generated.mode, "NODULE_RECALL")
        self.assertEqual(generated.selected, (7, 8, 9))
        self.assertEqual(generated.association_evidence, result)
        self.assertFalse(any(memory.expand(node["address"]) == (7, 8, 9)
                             for node in memory.snapshot()["nodes"]))
        self.assertEqual((memory.snapshot(), memory.learning_state()), before)

    def test_single_observed_payload_is_evoked_inside_a_new_context(self):
        memory = TrajectoryGenerationExperiment()
        cue = (1, 2, 3, 4)
        target = (7, 8, 9)
        source = memory.observe(cue, observation_id="source", stream_id="episode")
        answer = memory.observe(target, observation_id="later", stream_id="episode")
        query = (90, *cue, 91)
        before = memory.snapshot(), memory.learning_state()

        self.assertEqual(memory.associated_nodules(query).candidates, ())
        result = memory.generate(query)
        self.assertEqual(result.mode, "EMBEDDED_TEMPORAL_RECALL")
        self.assertEqual(result.selected, target)
        self.assertEqual(result.embedded_evidence.cue_payload_ids, (source.payload_id,))
        self.assertEqual(result.embedded_evidence.links[0].target_payload_id,
                         answer.payload_id)
        self.assertEqual(result.embedded_evidence.links[0].streams, ("episode",))
        self.assertEqual(memory.generate((90, *cue)).selected, target)
        self.assertEqual((memory.snapshot(), memory.learning_state()), before)
        for i in range(8):
            memory.observe(cue, observation_id=f"copy:{i}", stream_id=f"replay:{i}")
        self.assertEqual(memory.learning_state(), before[1])
        self.assertEqual(memory.generate(query), result)
        self.assertEqual(TrajectoryGenerationExperiment.restore(
            memory.snapshot()).generate(query), result)

    def test_longer_embedded_root_without_successor_does_not_hide_shorter_link(self):
        memory = TrajectoryGenerationExperiment()
        cue, target = (1, 2, 3), (7, 8, 9)
        larger = (90, *cue, 91)
        query = (88, *larger, 92)
        source = memory.observe(cue, observation_id="source", stream_id="episode")
        memory.observe(target, observation_id="target", stream_id="episode")
        memory.observe(larger, observation_id="larger", stream_id="other")
        before = memory.snapshot(), memory.learning_state()

        embedded = memory.embedded_root_relations(query)
        self.assertEqual(embedded.cue_payload_ids, (source.payload_id,))
        self.assertEqual([neighbor.symbols for neighbor in embedded.neighbors], [target])
        self.assertEqual(embedded.links[0].streams, ("episode",))
        result = memory.generate(query)
        self.assertEqual(result.mode, "EMBEDDED_TEMPORAL_RECALL")
        self.assertEqual(result.selected, target)
        self.assertEqual(result.embedded_evidence, embedded)
        self.assertEqual((memory.snapshot(), memory.learning_state()), before)
        self.assertEqual(TrajectoryGenerationExperiment.restore(
            before[0]).generate(query), result)

        for index in range(5):
            memory.observe(larger, observation_id=f"copy:{index}",
                           stream_id=f"copy:{index}")
        self.assertEqual(memory.learning_state(), before[1])
        self.assertEqual(memory.generate(query), result)

        closer = TrajectoryGenerationExperiment.restore(before[0])
        closer.observe((4, 5, 6), observation_id="larger-successor", stream_id="other")
        self.assertEqual([neighbor.symbols for neighbor in
                          closer.embedded_root_relations(query).neighbors],
                         [(4, 5, 6), target])
        self.assertEqual([neighbor.symbols for neighbor in
                          closer.embedded_root_relations(
                              query, include_shorter=False).neighbors], [(4, 5, 6)])

        peer = TrajectoryGenerationExperiment.restore(before[0])
        linked_peer = (4, 5, 6, 7, 8)  # Same length as the unlinked larger root.
        peer_target = (11, 12, 13)
        peer_source = peer.observe(linked_peer, observation_id="peer", stream_id="peer")
        peer.observe(peer_target, observation_id="peer-target", stream_id="peer")
        mixed_query = (87, *larger, 86, *linked_peer, 85)
        limited = peer.embedded_root_relations(mixed_query, limit=1)
        self.assertEqual(limited.cue_payload_ids, (peer_source.payload_id,))
        self.assertEqual([neighbor.symbols for neighbor in limited.neighbors], [peer_target])
        self.assertTrue(limited.truncated)  # Shorter linked cue was outside the limit.

        split = TrajectoryGenerationExperiment()
        split.observe(cue, observation_id="source", stream_id="one")
        split.observe(target, observation_id="target", stream_id="two")
        split.observe(larger, observation_id="larger", stream_id="three")
        self.assertEqual(split.generate(query).mode, "ECHO")

        reversed_memory = TrajectoryGenerationExperiment()
        reversed_memory.observe(target, observation_id="target", stream_id="one")
        reversed_memory.observe(cue, observation_id="source", stream_id="one")
        reversed_memory.observe(larger, observation_id="larger", stream_id="other")
        self.assertEqual(reversed_memory.generate(query).mode, "ECHO")

    def test_nested_linked_roots_keep_competing_destinations_across_scales(self):
        memory = TrajectoryGenerationExperiment()
        short, short_target = (1, 2, 3), (7, 8, 9)
        long, long_target = (90, *short, 91), (4, 5, 6)
        short_receipt = memory.observe(short, observation_id="short", stream_id="old")
        memory.observe(short_target, observation_id="short-target", stream_id="old")
        long_receipt = memory.observe(long, observation_id="long", stream_id="new")
        memory.observe(long_target, observation_id="long-target", stream_id="new")
        query = (88, *long, 92)
        before = memory.snapshot(), memory.learning_state()

        result = memory.generate(query)
        self.assertEqual(result.mode, "EMBEDDED_TEMPORAL_RECALL")
        self.assertEqual([candidate.output for candidate in result.candidates],
                         [long_target, short_target])
        self.assertEqual([candidate.log_score for candidate in result.candidates],
                         [0.0, 0.0])  # No cross-width probability ratio.
        self.assertEqual(result.embedded_evidence.cue_payload_ids,
                         (long_receipt.payload_id, short_receipt.payload_id))
        self.assertEqual([link.streams for link in result.embedded_evidence.links],
                         [("new",), ("old",)])
        self.assertEqual([neighbor.weight for neighbor in
                          result.embedded_evidence.neighbors], [1.0, 1.0])
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.selected)
        narrow = memory.generate(query, beam_width=1)
        self.assertEqual([candidate.output for candidate in narrow.candidates],
                         [long_target])
        self.assertTrue(narrow.truncated)
        self.assertIsNone(narrow.selected)
        self.assertEqual((memory.snapshot(), memory.learning_state()), before)
        for i in range(4):
            memory.observe(long, observation_id=f"copy:{i}", stream_id=f"copy:{i}")
        self.assertEqual(memory.learning_state(), before[1])
        self.assertEqual(memory.generate(query), result)
        self.assertEqual(TrajectoryGenerationExperiment.restore(
            memory.snapshot()).generate(query), result)

        split = TrajectoryGenerationExperiment()
        split.observe(short, observation_id="short", stream_id="old")
        split.observe(short_target, observation_id="target", stream_id="elsewhere")
        split.observe(long, observation_id="long", stream_id="new")
        split.observe(long_target, observation_id="target-long", stream_id="new")
        self.assertEqual([candidate.output for candidate in split.generate(query).candidates],
                         [long_target])
        reversed_memory = TrajectoryGenerationExperiment()
        reversed_memory.observe(short_target, observation_id="target", stream_id="old")
        reversed_memory.observe(short, observation_id="short", stream_id="old")
        reversed_memory.observe(long, observation_id="long", stream_id="new")
        reversed_memory.observe(long_target, observation_id="long-target", stream_id="new")
        self.assertEqual([candidate.output for candidate in
                          reversed_memory.generate(query).candidates], [long_target])

        # One destination can be witnessed from both widths in a single
        # capture. Its displayed weight comes from the longer cue once.
        shared = TrajectoryGenerationExperiment()
        shared.observe(short, observation_id="short", stream_id="shared")
        shared.observe(long, observation_id="long", stream_id="shared")
        shared.observe(short_target, observation_id="target", stream_id="shared")
        shared_links = shared.embedded_root_relations(query)
        matching = [neighbor for neighbor in shared_links.neighbors
                    if neighbor.symbols == short_target]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].weight, 1.0)
        self.assertEqual(sum(link.target_payload_id == matching[0].payload_id
                             for link in shared_links.links), 2)

    def test_embedded_roots_expose_competition_and_capture_boundaries(self):
        memory = TrajectoryGenerationExperiment()
        a, b = (1, 2, 3), (4, 5, 6)
        target_a, target_b = (7, 8, 9), (10, 11, 12)
        for i, (source, target) in enumerate(((a, target_a), (b, target_b))):
            memory.observe(source, observation_id=f"s:{i}", stream_id=f"stream:{i}")
            memory.observe(target, observation_id=f"t:{i}", stream_id=f"stream:{i}")
        query = (90, *a, 91, *b, 92)
        result = memory.generate(query)
        self.assertEqual(result.mode, "EMBEDDED_TEMPORAL_RECALL")
        self.assertEqual({candidate.output for candidate in result.candidates},
                         {target_a, target_b})
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.selected)
        self.assertEqual(len(result.embedded_evidence.cue_payload_ids), 2)
        self.assertTrue(memory.generate(query, beam_width=1).truncated)
        self.assertIsNone(memory.generate(query, beam_width=1).selected)

        split = TrajectoryGenerationExperiment()
        split.observe(a, observation_id="source", stream_id="one")
        split.observe(target_a, observation_id="target", stream_id="two")
        self.assertEqual(split.generate((90, *a, 91)).mode, "ECHO")
        reversed_memory = TrajectoryGenerationExperiment()
        reversed_memory.observe(target_a, observation_id="target", stream_id="one")
        reversed_memory.observe(a, observation_id="source", stream_id="one")
        self.assertEqual(reversed_memory.generate((90, *a, 91)).mode, "ECHO")
        self.assertEqual(memory.generate((90, 1, 91)).mode, "ECHO")

    def test_shorter_recurrent_cue_checks_apparent_unique_destination(self):
        memory = TrajectoryGenerationExperiment()
        short = (1, 2, 3)
        long = (90, *short, 91)
        a, b = (4, 5, 6), (7, 8, 9)
        for i in range(2):
            memory.observe((100 + i, *long, 200 + i),
                           observation_id=f"long:{i}", stream_id=f"long:{i}")
            memory.observe((300 + i, *a, 400 + i),
                           observation_id=f"a:{i}", stream_id=f"long:{i}")
            memory.observe((500 + i, *short, 600 + i),
                           observation_id=f"short:{i}", stream_id=f"short:{i}")
            memory.observe((700 + i, *b, 800 + i),
                           observation_id=f"b:{i}", stream_id=f"short:{i}")
        query = (88, *long, 92)
        stored = memory.snapshot(), memory.learning_state()
        primary = memory.associated_nodules(query)
        self.assertEqual(primary.selected, a)
        layered = memory.associated_nodules(query, include_shorter=True)
        self.assertEqual([candidate.symbols for candidate in layered.candidates], [a, b])
        self.assertTrue(layered.ambiguous)
        self.assertFalse(layered.truncated)
        self.assertEqual({stream for candidate in layered.candidates
                          for _, _, stream in candidate.witnesses},
                         {"long:0", "long:1", "short:0", "short:1"})
        result = memory.generate(query)
        self.assertEqual(result.mode, "NODULE_RECALL")
        self.assertEqual([candidate.output for candidate in result.candidates], [a, b])
        self.assertEqual([candidate.log_score for candidate in result.candidates],
                         [0.0, 0.0])
        self.assertEqual([candidate.source_width for candidate in
                          layered.candidates], [len(long), len(short)])
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.selected)
        self.assertEqual(result.association_evidence, layered)
        limited = memory.generate(query, beam_width=1)
        self.assertEqual([candidate.output for candidate in limited.candidates], [a])
        self.assertTrue(limited.truncated)
        self.assertIsNone(limited.selected)
        self.assertEqual((memory.snapshot(), memory.learning_state()), stored)
        for i in range(3):
            memory.observe((100, *long, 200), observation_id=f"copy:{i}",
                           stream_id=f"copy:{i}")
        self.assertEqual(memory.learning_state(), stored[1])
        self.assertEqual(memory.generate(query), result)
        self.assertEqual(TrajectoryGenerationExperiment.restore(
            memory.snapshot()).generate(query), result)

        split = TrajectoryGenerationExperiment()
        split.observe((100, *long, 200), observation_id="long", stream_id="long")
        split.observe((300, *a, 400), observation_id="a", stream_id="long")
        split.observe((101, *long, 201), observation_id="long:2", stream_id="long:2")
        split.observe((301, *a, 401), observation_id="a:2", stream_id="long:2")
        split.observe((500, *short, 600), observation_id="short", stream_id="short")
        split.observe((700, *b, 800), observation_id="b", stream_id="elsewhere")
        self.assertEqual([candidate.output for candidate in split.generate(query).candidates],
                         [a])

        converged = TrajectoryGenerationExperiment()
        for i in range(2):
            converged.observe((100 + i, *long, 200 + i),
                              observation_id=f"long:{i}", stream_id=f"long:{i}")
            converged.observe((300 + i, *a, 400 + i),
                              observation_id=f"a:{i}", stream_id=f"long:{i}")
            converged.observe((500 + i, *short, 600 + i),
                              observation_id=f"short:{i}", stream_id=f"short:{i}")
            converged.observe((700 + i, *a, 800 + i),
                              observation_id=f"same:{i}", stream_id=f"short:{i}")
        direct = converged.associated_nodules(query)
        all_scales = converged.associated_nodules(query, include_shorter=True)
        self.assertEqual([candidate.symbols for candidate in all_scales.candidates], [a])
        self.assertEqual(all_scales.candidates[0].weight, direct.candidates[0].weight)
        self.assertEqual(len(all_scales.candidates[0].witnesses), 4)
        self.assertEqual(all_scales.selected, a)
        self.assertEqual(converged.generate(query).selected, a)

    def test_full_root_and_shorter_recurrent_cue_keep_distinct_targets(self):
        memory = TrajectoryGenerationExperiment()
        source, direct, recurrent = (1, 2, 3, 4), (7, 8, 9), (5, 6)
        events = (
            (source, "direct"), (direct, "direct"),
            ((90, 2, 3, 91), "recurrent"), ((93, *recurrent, 94), "recurrent"),
            ((92, 2, 3, 95), "recurrent"), ((96, *recurrent, 97), "recurrent"),
        )
        for index, (payload, stream) in enumerate(events):
            memory.observe(payload, observation_id=str(index), stream_id=stream)
        query = (100, *source, 101)
        before = memory.snapshot(), memory.learning_state()

        result = memory.generate(query)
        self.assertEqual(result.mode, "COMBINED_RECALL")
        self.assertEqual([candidate.output for candidate in result.candidates],
                         [direct, recurrent])
        self.assertEqual([candidate.stop_reason for candidate in result.candidates],
                         ["embedded_root_relation", "nodule_association"])
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.selected)
        self.assertEqual(result.embedded_evidence.links[0].streams, ("direct",))
        witnesses = result.association_evidence.candidates[0].witnesses
        self.assertTrue(witnesses)
        self.assertEqual({stream for _, _, stream in witnesses}, {"recurrent"})
        narrow = memory.generate(query, beam_width=1)
        self.assertEqual([candidate.output for candidate in narrow.candidates], [direct])
        self.assertTrue(narrow.truncated)
        self.assertIsNone(narrow.selected)
        self.assertEqual(narrow.association_evidence.candidates[0].symbols, recurrent)
        self.assertEqual((memory.snapshot(), memory.learning_state()), before)
        for index in range(6):
            memory.observe(source, observation_id=f"copy:{index}",
                           stream_id=f"unrelated:{index}")
        self.assertEqual(memory.learning_state(), before[1])
        self.assertEqual(memory.generate(query), result)
        self.assertEqual(TrajectoryGenerationExperiment.restore(
            memory.snapshot()).generate(query), result)

    def test_same_target_from_full_and_recurrent_cues_is_not_double_counted(self):
        memory = TrajectoryGenerationExperiment()
        source, target = (1, 2, 3, 4), (7, 8, 9)
        events = (
            (source, "direct"), (target, "direct"),
            ((90, 2, 3, 91), "recurrent"), ((93, *target, 94), "recurrent"),
            ((92, 2, 3, 95), "recurrent"), ((96, *target, 97), "recurrent"),
        )
        for index, (payload, stream) in enumerate(events):
            memory.observe(payload, observation_id=str(index), stream_id=stream)

        result = memory.generate((100, *source, 101))
        self.assertEqual(result.mode, "COMBINED_RECALL")
        self.assertEqual([candidate.output for candidate in result.candidates], [target])
        self.assertEqual(result.selected, target)
        self.assertFalse(result.ambiguous)
        self.assertFalse(result.truncated)
        self.assertEqual(result.embedded_evidence.neighbors[0].symbols, target)
        self.assertEqual(result.association_evidence.candidates[0].symbols, target)

    def test_online_interposed_input_cannot_hide_earlier_cross_capture_route(self):
        memory = TrajectoryGenerationExperiment()
        cue, target, interposed = (1, 2, 3), (7, 8, 9), (4, 5, 6)
        for index in range(2):
            memory.observe((100 + index, *cue, 200 + index),
                           observation_id=f"cue:{index}", stream_id=f"ep:{index}")
            memory.observe((300 + index, *target, 400 + index),
                           observation_id=f"target:{index}", stream_id=f"ep:{index}")

        new_cue = (102, *cue, 202)
        before = memory.generate(new_cue)
        self.assertEqual(before.mode, "NODULE_RECALL")
        self.assertEqual(before.selected, target)
        memory.observe(new_cue, observation_id="cue:2", stream_id="ep:2")
        self.assertEqual(memory.generate(new_cue).selected, target)
        same_target = TrajectoryGenerationExperiment.restore(memory.snapshot())
        same_target.observe(target, observation_id="target:2", stream_id="ep:2")
        converged = same_target.generate(new_cue)
        self.assertEqual(converged.mode, "COMBINED_RECALL")
        self.assertEqual([candidate.output for candidate in converged.candidates], [target])
        self.assertEqual(converged.selected, target)
        memory.observe(interposed, observation_id="interposed:2", stream_id="ep:2")
        stored = memory.snapshot(), memory.learning_state()

        result = memory.generate(new_cue)
        self.assertEqual(result.mode, "COMBINED_RECALL")
        self.assertEqual([candidate.output for candidate in result.candidates],
                         [interposed, target])
        self.assertEqual([candidate.stop_reason for candidate in result.candidates],
                         ["temporal_recall", "nodule_association"])
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.selected)
        self.assertEqual(result.temporal_evidence[0].streams, ("ep:2",))
        self.assertEqual({stream for candidate in result.association_evidence.candidates
                          for _, _, stream in candidate.witnesses}, {"ep:0", "ep:1"})
        self.assertEqual((memory.snapshot(), memory.learning_state()), stored)
        narrow = memory.generate(new_cue, beam_width=1)
        self.assertEqual(narrow.candidates[0].output, interposed)
        self.assertTrue(narrow.truncated)
        self.assertIsNone(narrow.selected)
        self.assertEqual(narrow.association_evidence.candidates[0].symbols, target)

        for index in range(5):
            memory.observe(new_cue, observation_id=f"copy:{index}",
                           stream_id=f"unrelated:{index}")
        self.assertEqual(memory.learning_state(), stored[1])
        self.assertEqual(memory.generate(new_cue), result)
        self.assertEqual(TrajectoryGenerationExperiment.restore(
            memory.snapshot()).generate(new_cue), result)

        split = TrajectoryGenerationExperiment.restore(stored[0])
        split.observe((103, *cue, 203), observation_id="cue:split",
                      stream_id="another")
        split.observe((10, 11, 12), observation_id="other:split",
                      stream_id="separate")
        self.assertEqual(split.generate((103, *cue, 203)).selected, target)

    def test_continuation_cannot_hide_recurrent_route_from_other_captures(self):
        memory = TrajectoryGenerationExperiment()
        cue, target = (1, 2, 3), (7, 8, 9)
        for index in range(2):
            stream = f"episode:{index}"
            memory.observe((100 + index, *cue, 200 + index),
                           observation_id=f"cue:{index}", stream_id=stream)
            memory.observe((300 + index, *target, 400 + index),
                           observation_id=f"target:{index}", stream_id=stream)
        query = (102, *cue, 202)
        self.assertEqual(memory.generate(query).selected, target)

        continuation_source = (88, *query, 42)
        memory.observe(continuation_source, observation_id="continuation", stream_id="other")
        stored = memory.snapshot(), memory.learning_state()
        result = memory.generate(query)
        self.assertEqual(result.mode, "COMBINED_ROUTES")
        self.assertEqual([candidate.output for candidate in result.candidates],
                         [(*query, 42), target])
        self.assertEqual(result.candidates[0].continuation, (42,))
        self.assertEqual(result.candidates[1].stop_reason, "nodule_association")
        self.assertEqual({stream for _, _, stream in
                          result.association_evidence.candidates[0].witnesses},
                         {"episode:0", "episode:1"})
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.selected)
        self.assertEqual((memory.snapshot(), memory.learning_state()), stored)

        narrow = memory.generate(query, beam_width=1)
        self.assertEqual(narrow.mode, "COMBINED_ROUTES")
        self.assertEqual([candidate.output for candidate in narrow.candidates],
                         [(*query, 42)])
        self.assertTrue(narrow.truncated)
        self.assertIsNone(narrow.selected)
        self.assertEqual(narrow.association_evidence.candidates[0].symbols, target)

        for index in range(5):
            memory.observe(continuation_source, observation_id=f"copy:{index}",
                           stream_id=f"copy:{index}")
        self.assertEqual(memory.learning_state(), stored[1])
        self.assertEqual(memory.generate(query), result)
        self.assertEqual(TrajectoryGenerationExperiment.restore(
            memory.snapshot()).generate(query), result)

        isolated = TrajectoryGenerationExperiment()
        isolated.observe((100, *cue, 200), observation_id="cue", stream_id="a")
        isolated.observe((300, *target, 400), observation_id="target", stream_id="b")
        isolated.observe(continuation_source, observation_id="continuation",
                         stream_id="other")
        self.assertEqual(isolated.generate(query).mode, "CONTINUATION")

    def test_new_longer_cue_without_successor_keeps_older_shorter_route(self):
        memory = TrajectoryGenerationExperiment()
        cue, target = (1, 2, 3), (7, 8, 9)
        for index in range(2):
            stream = f"episode:{index}"
            memory.observe((100 + index, *cue, 200 + index),
                           observation_id=f"cue:{index}", stream_id=stream)
            memory.observe((300 + index, *target, 400 + index),
                           observation_id=f"target:{index}", stream_id=stream)
        query = (102, *cue, 202)
        self.assertEqual(memory.associated_nodules(query).selected, target)

        memory.observe(query, observation_id="new-cue", stream_id="current")
        memory.observe((88, *query, 42), observation_id="extension",
                       stream_id="separate")
        before = memory.snapshot(), memory.learning_state()
        association = memory.associated_nodules(query)
        self.assertEqual(association.selected, target)
        self.assertEqual({stream for _, _, stream in association.candidates[0].witnesses},
                         {"episode:0", "episode:1"})
        result = memory.generate(query)
        self.assertEqual(result.mode, "COMBINED_ROUTES")
        self.assertEqual({candidate.output for candidate in result.candidates},
                         {query, (*query, 42), target})
        self.assertIsNone(result.selected)
        self.assertEqual((memory.snapshot(), memory.learning_state()), before)
        self.assertEqual(TrajectoryGenerationExperiment.restore(
            before[0]).generate(query), result)

    def test_exact_embedded_and_recurrent_routes_remain_separate(self):
        memory = TrajectoryGenerationExperiment()
        cue, recurrent, embedded, exact = (1, 2, 3), (7, 8, 9), (11, 12), (4, 5, 6)
        memory.observe(cue, observation_id="embedded:source", stream_id="older")
        memory.observe(embedded, observation_id="embedded:target", stream_id="older")
        for index in range(2):
            memory.observe((100 + index, *cue, 200 + index),
                           observation_id=f"recurring:source:{index}",
                           stream_id=f"episode:{index}")
            memory.observe((300 + index, *recurrent, 400 + index),
                           observation_id=f"recurring:target:{index}",
                           stream_id=f"episode:{index}")
        query = (102, *cue, 202)
        memory.observe(query, observation_id="exact:source", stream_id="current")
        memory.observe(exact, observation_id="exact:target", stream_id="current")

        result = memory.generate(query)
        self.assertEqual(result.mode, "COMBINED_RECALL")
        self.assertEqual([candidate.output for candidate in result.candidates],
                         [exact, embedded, recurrent])
        self.assertEqual([candidate.stop_reason for candidate in result.candidates],
                         ["temporal_recall", "embedded_root_relation", "nodule_association"])
        self.assertIsNone(result.selected)
        self.assertEqual(result.temporal_evidence[0].streams, ("current",))
        self.assertEqual(result.embedded_evidence.links[0].streams, ("older",))
        self.assertIsNotNone(result.association_evidence)
        narrow = memory.generate(query, beam_width=2)
        self.assertTrue(narrow.truncated)
        self.assertEqual([candidate.output for candidate in narrow.candidates],
                         [exact, embedded])
        self.assertIsNone(narrow.selected)

    def test_route_stability_counts_distinct_contexts_without_deciding_truth(self):
        memory = TrajectoryGenerationExperiment()
        cue, frequent, competing = (1, 2, 3), (7, 8, 9), (4, 5, 6)
        observation = 0
        for label, target, count in (("frequent", frequent, 4),
                                     ("competing", competing, 2)):
            for index in range(count):
                stream = f"{label}:{index}"
                memory.observe((1000 + observation, *cue, 2000 + observation),
                               observation_id=f"{observation}:source", stream_id=stream)
                memory.observe((3000 + observation, *target, 4000 + observation),
                               observation_id=f"{observation}:target", stream_id=stream)
                observation += 1
        query = (9000, *cue, 9001)
        before = memory.route_stability(query)

        self.assertTrue(before.ambiguous)
        self.assertFalse(before.truncated)
        self.assertEqual(before.strongest, frequent)
        self.assertEqual(before.cross_stream_strongest, frequent)
        self.assertEqual([candidate.symbols for candidate in before.candidates],
                         [frequent, competing])
        self.assertEqual([candidate.witness_pairs for candidate in before.candidates],
                         [4, 2])
        self.assertEqual([len(candidate.independent_streams)
                          for candidate in before.candidates], [4, 2])
        self.assertAlmostEqual(before.candidates[0].weight_share, 2 / 3)
        self.assertAlmostEqual(before.candidates[1].weight_share, 1 / 3)
        self.assertAlmostEqual(before.candidates[0].rank_share, 2 / 3)
        self.assertAlmostEqual(before.candidates[1].rank_share, 1 / 3)
        generated = memory.generate(query)
        self.assertEqual(generated.mode, "NODULE_RECALL")
        self.assertTrue(generated.ambiguous)
        self.assertIsNone(generated.selected)

        learned = memory.learning_state()
        repeated_payload = (1000, *cue, 2000)
        for index in range(12):
            memory.observe(repeated_payload, observation_id=f"copy:{index}",
                           stream_id=f"copy-stream:{index}")
        self.assertEqual(memory.learning_state(), learned)
        self.assertEqual(memory.route_stability(query), before)

        stream = "frequent:new"
        memory.observe((8000, *cue, 8001), observation_id="new:source", stream_id=stream)
        memory.observe((8002, *frequent, 8003), observation_id="new:target", stream_id=stream)
        after = memory.route_stability(query)
        self.assertEqual([candidate.witness_pairs for candidate in after.candidates], [5, 2])
        self.assertGreater(after.candidates[0].rank_share, before.candidates[0].rank_share)
        self.assertTrue(after.ambiguous)
        self.assertIsNone(memory.generate(query).selected)
        self.assertEqual(TrajectoryGenerationExperiment.restore(
            memory.snapshot()).route_stability(query), after)

    def test_text_adapter_discovers_longer_recurrent_spans_without_word_rules(self):
        memory = TrajectoryGenerationExperiment()
        for i, text in enumerate((
            "no quarto ensolarado", "a cama está arrumada",
            "este quarto é claro", "uma cama com cobertor",
        )):
            memory.observe(text_symbols(text), observation_id=str(i))
        query = text_symbols("pensei no quarto durante a viagem!")
        result = memory.associated_nodules(query)
        self.assertEqual(result.depth, 1)
        self.assertEqual("".join(map(chr, result.candidates[0].symbols)), "a cama ")
        self.assertEqual(len(result.candidates[0].witnesses), 3)
        self.assertTrue(result.ambiguous)
        self.assertTrue(result.truncated)
        self.assertIsNone(result.selected)
        self.assertEqual(memory.generate(query).mode, "NODULE_RECALL")
        self.assertIsNone(memory.generate(query).selected)

    def test_distinct_contexts_reinforce_compositions_but_copies_do_not(self):
        memory = TrajectoryGenerationExperiment()
        for i, payload in enumerate(((90, 1, 2, 3, 91), (94, 7, 8, 9, 95),
                                     (92, 1, 2, 3, 93), (96, 7, 8, 9, 97))):
            memory.observe(payload, observation_id=str(i))
        query = (100, 1, 2, 3, 101)
        before = memory.associated_nodules(query)
        learned = memory.learning_state()
        for i in range(12):
            memory.observe((90, 1, 2, 3, 91), observation_id=f"copy:{i}",
                           stream_id=f"new:{i}")
        self.assertEqual(memory.learning_state(), learned)
        self.assertEqual(memory.associated_nodules(query), before)
        memory.observe((98, 1, 2, 3, 99), observation_id="new-source")
        memory.observe((110, 7, 8, 9, 111), observation_id="new-target")
        after = memory.associated_nodules(query)
        target = next(c for c in after.candidates if c.symbols == (7, 8, 9))
        self.assertGreater(target.weight, before.candidates[0].weight)
        self.assertGreater(len(target.witnesses), len(before.candidates[0].witnesses))

    def test_reused_target_forms_new_intermediate_pair_without_reinforcing_old_pair(self):
        memory = TrajectoryGenerationExperiment()
        cue, target = (1, 2, 3), (7, 8, 9)
        known_target = (70, *target, 71)
        memory.observe(known_target, observation_id="known", stream_id="archive")
        memory.observe((72, *target, 73), observation_id="other-target",
                       stream_id="other-archive")
        memory.observe((10, *cue, 11), observation_id="cue-pattern",
                       stream_id="cue-archive")
        novel_source = (12, *cue, 13)
        source_receipt = memory.observe(novel_source, observation_id="new-source",
                                        stream_id="live")
        query = (90, *cue, 91)
        self.assertEqual(memory.associated_nodules(query).candidates, ())
        before_content = memory.learning_state()["learned_payloads"]
        copy = memory.observe(known_target, observation_id="reused-target",
                              stream_id="live")
        self.assertFalse(copy.learned)
        self.assertEqual(memory.learning_state()["learned_payloads"], before_content)
        first = memory.associated_nodules(query)
        self.assertEqual(first.selected, target)
        self.assertIn((source_receipt.payload_id, copy.payload_id, "live"),
                      first.candidates[0].witnesses)
        first_weight = first.candidates[0].weight
        memory.observe(novel_source, observation_id="repeat-source", stream_id="replay")
        memory.observe(known_target, observation_id="repeat-target", stream_id="replay")
        repeated = memory.associated_nodules(query)
        self.assertAlmostEqual(repeated.candidates[0].weight, first_weight)
        self.assertEqual(memory.route_stability(query).candidates[0].witness_pairs, 1)
        self.assertEqual(TrajectoryGenerationExperiment.restore(memory.snapshot())
                         .associated_nodules(query), repeated)

        reverse = TrajectoryGenerationExperiment()
        for i, payload in enumerate((known_target, (72, *target, 73),
                                     (10, *cue, 11), novel_source)):
            reverse.observe(payload, observation_id=f"base:{i}",
                            stream_id=f"base:{i}")
        reverse.observe(known_target, observation_id="target-first", stream_id="reverse")
        reverse.observe(novel_source, observation_id="source-last", stream_id="reverse")
        self.assertEqual(reverse.associated_nodules(query).candidates, ())

        distant = TrajectoryGenerationExperiment()
        for index, payload in enumerate((known_target, (72, *target, 73),
                                         (10, *cue, 11), (80, 81, 82))):
            distant.observe(payload, observation_id=f"known:{index}",
                            stream_id=f"archive:{index}")
        distant.observe(novel_source, observation_id="cue", stream_id="live")
        distant.observe((80, 81, 82), observation_id="interposed", stream_id="live")
        distant.observe(known_target, observation_id="target", stream_id="live")
        self.assertAlmostEqual(distant.associated_nodules(query).candidates[0].weight,
                               first_weight * exp(-0.35))

    def test_intermediate_association_is_directed_and_capture_local(self):
        forward = TrajectoryGenerationExperiment()
        reverse = TrajectoryGenerationExperiment()
        split = TrajectoryGenerationExperiment()
        source = ((90, 1, 2, 3, 91), (92, 1, 2, 3, 93))
        target = ((94, 7, 8, 9, 95), (96, 7, 8, 9, 97))
        for i, payload in enumerate((source[0], target[0], source[1], target[1])):
            forward.observe(payload, observation_id=str(i))
        for i, payload in enumerate((*target, *source)):
            reverse.observe(payload, observation_id=str(i))
        for i, payload in enumerate((source[0], target[0], source[1], target[1])):
            split.observe(payload, observation_id=str(i),
                          stream_id="source" if i % 2 == 0 else "target")
        query = (100, 1, 2, 3, 101)
        self.assertEqual(forward.associated_nodules(query).selected, (7, 8, 9))
        self.assertEqual(reverse.associated_nodules(query).candidates, ())
        self.assertEqual(split.associated_nodules(query).candidates, ())
        self.assertEqual(split.generate(query).mode, "ECHO")

    def test_temporal_distraction_decreases_nodule_weight(self):
        def memory(with_distraction):
            result = TrajectoryGenerationExperiment()
            payloads = [(90, 1, 2, 3, 91), (94, 7, 8, 9, 95),
                        (92, 1, 2, 3, 93), (96, 7, 8, 9, 97)]
            if with_distraction:
                payloads.insert(1, (200, 201, 202, 203))
            for i, payload in enumerate(payloads):
                result.observe(payload, observation_id=str(i))
            return result

        query = (100, 1, 2, 3, 101)
        close = memory(False).associated_nodules(query)
        distant = memory(True).associated_nodules(query)
        self.assertGreater(close.candidates[0].weight, distant.candidates[0].weight)
        self.assertEqual(close.candidates[0].symbols, distant.candidates[0].symbols)
        self.assertEqual(len(close.candidates[0].witnesses), len(distant.candidates[0].witnesses))

    def test_competing_intermediate_associations_remain_alternatives(self):
        memory = TrajectoryGenerationExperiment()
        for i, payload in enumerate((
            (90, 1, 2, 3, 91), (100, 7, 8, 9, 101),
            (92, 1, 2, 3, 93), (102, 11, 12, 13, 103),
            (94, 1, 2, 3, 95), (104, 7, 8, 9, 105),
            (96, 1, 2, 3, 97), (106, 11, 12, 13, 107),
        )):
            memory.observe(payload, observation_id=str(i))
        query = (200, 1, 2, 3, 201)
        result = memory.associated_nodules(query)
        self.assertTrue(result.ambiguous)
        self.assertFalse(result.truncated)
        self.assertIsNone(result.selected)
        self.assertEqual({c.symbols for c in result.candidates}, {(7, 8, 9), (11, 12, 13)})
        generated = memory.generate(query)
        self.assertEqual(generated.mode, "NODULE_RECALL")
        self.assertTrue(generated.ambiguous)
        self.assertIsNone(generated.selected)

    def test_overlapping_compositions_do_not_create_false_within_edge(self):
        memory = TrajectoryGenerationExperiment()
        for i, payload in enumerate(((0, 1, 2, 3, 4, 7, 8, 9, 50),
                                     (99, 1, 2, 3, 4, 7, 8, 9, 51))):
            memory.observe(payload, observation_id=str(i))
        result = memory.associated_nodules((1, 2, 3), channel="within")
        self.assertEqual(result.depth, 1)
        self.assertFalse(any(c.symbols == (2, 3, 4) for c in result.candidates))
        target = next(c for c in result.candidates if c.symbols == (4, 7, 8, 9))
        self.assertAlmostEqual(target.weight, 2.0)  # Adjacent [1,2,3] -> [4,7,8,9].
        self.assertEqual(len(target.witnesses), 2)
        self.assertTrue(all(left == right for left, right, _ in target.witnesses))

    def test_longer_recurring_nodules_activate_their_own_scale(self):
        memory = TrajectoryGenerationExperiment()
        source = tuple(range(1, 10))
        target = tuple(range(21, 30))
        for i, payload in enumerate(((90,) + source + (91,), (92,) + target + (93,),
                                     (94,) + source + (95,), (96,) + target + (97,))):
            memory.observe(payload, observation_id=str(i))
        query = (300,) + source + (301,)
        result = memory.associated_nodules(query)
        self.assertGreaterEqual(result.depth, 2)
        self.assertEqual(result.selected, target)
        self.assertEqual(memory.generate(query).selected, target)

    def test_deeper_cue_preserves_shorter_targets_from_another_scale(self):
        source = (1, 2, 3, 4, 5)
        short = (7, 8, 9)
        long = (11, 12, 13, 14, 15)
        query = (500, *source, 600)

        def learn(targets):
            memory = TrajectoryGenerationExperiment()
            for i, target in enumerate(targets):
                memory.observe((100 + i, *source, 200 + i), observation_id=f"s:{i}")
                memory.observe((300 + i, *target, 400 + i), observation_id=f"t:{i}")
            return memory

        clean = learn((short,) * 4)
        recalled = clean.associated_nodules(query)
        self.assertGreaterEqual(recalled.depth, 2)
        self.assertEqual(recalled.selected, short)
        self.assertEqual(clean.generate(query).selected, short)

        competing = learn((short, long, short, long)).associated_nodules(query)
        self.assertGreaterEqual(competing.depth, 2)
        self.assertEqual({candidate.symbols for candidate in competing.candidates},
                         {short, long})
        self.assertTrue(competing.ambiguous)
        self.assertIsNone(competing.selected)
        self.assertAlmostEqual(competing.total_rank_score,
                               sum(candidate.rank_score for candidate in competing.candidates))

    def test_two_hop_nodule_path_requires_exact_middle_payload_and_capture(self):
        memory = TrajectoryGenerationExperiment()
        a, b = (1, 2, 3, 4, 5), (1, 2, 6, 7, 8)
        target_a, target_b = (9, 10, 11), (12, 13, 14)
        expected_chains = set()
        for i in range(4):
            source = memory.observe((100 + i, *a, 200 + i),
                                    observation_id=f"a:{i}:0", stream_id=f"a:{i}")
            middle = memory.observe((300 + i, *b, 400 + i),
                                    observation_id=f"a:{i}:1", stream_id=f"a:{i}")
            target = memory.observe((500 + i, *target_a, 600 + i),
                                    observation_id=f"a:{i}:2", stream_id=f"a:{i}")
            expected_chains.add((f"a:{i}",
                                 (source.payload_id, middle.payload_id, target.payload_id)))
            memory.observe((700 + i, *b, 800 + i),
                           observation_id=f"b:{i}:0", stream_id=f"b:{i}")
            memory.observe((900 + i, *target_b, 1000 + i),
                           observation_id=f"b:{i}:1", stream_id=f"b:{i}")

        query = (1100, *a, 1101)
        before = memory.snapshot(), memory.learning_state()
        traced = memory.trace_nodule_paths(query)
        paths = {path.nodules: path for path in traced.paths}
        self.assertEqual(set(paths), {(b,), (target_a,), (b, target_a)})
        self.assertEqual(set(paths[(b, target_a)].witnesses), expected_chains)
        self.assertEqual(paths[(b, target_a)].supporting_streams,
                         tuple(f"a:{i}" for i in range(4)))
        self.assertNotIn((b, target_b), paths)  # B→target B exists elsewhere.
        self.assertFalse(traced.truncated)
        self.assertEqual((memory.snapshot(), memory.learning_state()), before)
        self.assertEqual({path.nodules for path in memory.trace_nodule_paths(
            query, max_hops=1).paths}, {(b,), (target_a,)})
        self.assertTrue(memory.trace_nodule_paths(query, limit=1).truncated)

        reopened = TrajectoryGenerationExperiment.restore(memory.snapshot())
        self.assertEqual(reopened.trace_nodule_paths(query), traced)

    def test_repeated_middle_must_be_the_same_occurrence_in_a_two_hop_path(self):
        memory = TrajectoryGenerationExperiment()
        a, b, c = (1, 2, 3), (7, 8, 9), (4, 5, 6)
        roots = ((10, *a, 11), (20, *b, 21), (30, *c, 31))
        for index, motif in enumerate((a, b, c)):
            memory.observe((40 + index, *motif, 50 + index),
                           observation_id=f"pattern:{index}",
                           stream_id=f"archive:{index}")
        for index, root in enumerate(roots):
            memory.observe(root, observation_id=f"known:{index}",
                           stream_id=f"known:{index}")
        # B->C occurs before A->B. The two B references name the same payload,
        # but they are separate occurrences and cannot form an A->B->C path.
        for index, root in enumerate((roots[1], roots[2], roots[0], roots[1])):
            memory.observe(root, observation_id=f"reversed:{index}", stream_id="reversed")
        query = (90, *a, 91)
        wrong = memory.trace_nodule_paths(query)
        self.assertFalse(any(path.nodules == (b, c) for path in wrong.paths))
        before = memory.route_stability(query)
        for index, root in enumerate(roots):
            memory.observe(root, observation_id=f"valid:{index}", stream_id="valid")
        paths = memory.trace_nodule_paths(query).paths
        joined = next(path for path in paths if path.nodules == (b, c))
        self.assertEqual(joined.supporting_streams, ("valid",))
        self.assertEqual(memory.route_stability(query).candidates[0].weight,
                         before.candidates[0].weight)

    def test_shared_nodule_does_not_stitch_two_different_captures(self):
        memory = TrajectoryGenerationExperiment()
        a, b, c = (1, 2, 3), (4, 5, 6), (7, 8, 9)
        for i in range(2):
            memory.observe((100 + i, *a, 200 + i),
                           observation_id=f"x:{i}:a", stream_id=f"x:{i}")
            memory.observe((300 + i, *b, 400 + i),
                           observation_id=f"x:{i}:b", stream_id=f"x:{i}")
            memory.observe((500 + i, *b, 600 + i),
                           observation_id=f"y:{i}:b", stream_id=f"y:{i}")
            memory.observe((700 + i, *c, 800 + i),
                           observation_id=f"y:{i}:c", stream_id=f"y:{i}")
        trace = memory.trace_nodule_paths((1000, *a, 1001))
        self.assertEqual({path.nodules for path in trace.paths}, {(b,)})
        self.assertEqual(memory.trace_nodule_paths((2000, 2001)).paths, ())
        with self.assertRaises(ValueError):
            memory.trace_nodule_paths((1000, *a, 1001), max_hops=3)

    def test_nodule_recall_survives_reopen_and_symbol_renaming(self):
        payloads = ((90, 1, 2, 3, 91), (94, 7, 8, 9, 95),
                    (92, 1, 2, 3, 93), (96, 7, 8, 9, 97))
        query = (100, 1, 2, 3, 101)
        memory, renamed = TrajectoryGenerationExperiment(), TrajectoryGenerationExperiment()
        mapping = {symbol: symbol * 101 + 17 for payload in (*payloads, query) for symbol in payload}
        for i, payload in enumerate(payloads):
            memory.observe(payload, observation_id=str(i))
            renamed.observe(tuple(mapping[symbol] for symbol in payload), observation_id=str(i))
        original = memory.associated_nodules(query)
        transformed = renamed.associated_nodules(tuple(mapping[symbol] for symbol in query))
        self.assertEqual(original.candidates[0].weight, transformed.candidates[0].weight)
        self.assertEqual(tuple(mapping[symbol] for symbol in original.selected), transformed.selected)
        self.assertEqual(original.depth, transformed.depth)
        with tempfile.TemporaryDirectory() as directory:
            store = ContentAddressedStatePersistence(
                Path(directory), namespace="nodule-association-test", backend="sqlite",
                allow_fallback=False,
            )
            receipt = memory.save(store)
            reopened = TrajectoryGenerationExperiment.load(store, receipt)
        self.assertEqual(reopened.associated_nodules(query), original)
        self.assertEqual(reopened.generate(query), memory.generate(query))

    def test_no_nodule_association_without_recurrence_or_between_hierarchies(self):
        memory = TrajectoryGenerationExperiment()
        memory.observe((90, 1, 2, 3, 91), observation_id="one", hierarchy_id="h1")
        memory.observe((92, 7, 8, 9, 93), observation_id="two", hierarchy_id="h2")
        query = (100, 1, 2, 3, 101)
        self.assertEqual(memory.associated_nodules(query, hierarchy_id="h1").candidates, ())
        self.assertEqual(memory.associated_nodules(query, hierarchy_id="h2").candidates, ())
        self.assertEqual(memory.generate(query, hierarchy_id="h1").mode, "ECHO")
        with self.assertRaises(ValueError):
            memory.associated_nodules(query, channel="unknown")
        with self.assertRaises(ValueError):
            memory.associated_nodules(query, limit=0)


if __name__ == "__main__":
    unittest.main()
