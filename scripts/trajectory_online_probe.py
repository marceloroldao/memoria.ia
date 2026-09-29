#!/usr/bin/env python3
"""Online probe for exact-root, continuation and recurrent-nodule competition."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from random import Random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memoria_resolutiva.trajectory_generation_v2 import TrajectoryGenerationExperiment


def trial(rng: Random) -> dict[str, bool]:
    sizes = (rng.randrange(2, 6), rng.randrange(2, 6), rng.randrange(2, 6))
    symbols = iter(rng.sample(range(10_000, 900_000), sum(sizes)))
    cue, target, interposed = (tuple(next(symbols) for _ in range(size))
                               for size in sizes)

    def wrapped(motif: tuple[int, ...]) -> tuple[int, ...]:
        return (rng.randrange(1_000_000, 2_000_000), *motif,
                rng.randrange(2_000_000, 3_000_000))

    memory = TrajectoryGenerationExperiment()
    for episode in range(2):
        memory.observe(wrapped(cue), observation_id=f"cue:{episode}",
                       stream_id=f"episode:{episode}")
        memory.observe(wrapped(target), observation_id=f"target:{episode}",
                       stream_id=f"episode:{episode}")

    new_input = wrapped(cue)
    before_input = memory.generate(new_input)
    continuation_memory = TrajectoryGenerationExperiment.restore(memory.snapshot())
    continuation_tail = rng.randrange(4_000_000, 5_000_000)
    continuation_source = (rng.randrange(3_000_000, 4_000_000),
                           *new_input, continuation_tail)
    continuation_memory.observe(continuation_source, observation_id="continuation",
                                stream_id="unrelated")
    continuation_state = (continuation_memory.snapshot(),
                          continuation_memory.learning_state())
    with_continuation = continuation_memory.generate(new_input)
    continuation_limited = continuation_memory.generate(new_input, beam_width=1)
    continuation_witnesses = (
        with_continuation.association_evidence.candidates[0].witnesses
        if with_continuation.association_evidence else ()
    )
    continuation_read_only = (
        continuation_memory.snapshot(), continuation_memory.learning_state()
    ) == continuation_state
    for index in range(3):
        continuation_memory.observe(continuation_source, observation_id=f"repeat:{index}",
                                    stream_id=f"repeat:{index}")
    continuation_duplicates_unchanged = (
        continuation_memory.learning_state() == continuation_state[1]
        and continuation_memory.generate(new_input) == with_continuation
    )
    longer_cue_memory = TrajectoryGenerationExperiment.restore(continuation_state[0])
    longer_cue_memory.observe(new_input, observation_id="longer-cue",
                              stream_id="new-capture")
    longer_association = longer_cue_memory.associated_nodules(new_input)
    longer_result = longer_cue_memory.generate(new_input)

    pruned_memory = TrajectoryGenerationExperiment()
    pruned_memory.observe(new_input, observation_id="source", stream_id="live")
    pruned_memory.observe(interposed, observation_id="successor", stream_id="live")
    pruned_memory.observe(continuation_source, observation_id="extension",
                          stream_id="unrelated")
    for index in range(3):
        pruned_memory.observe((rng.randrange(5_000_000, 6_000_000), *new_input),
                              observation_id=f"end:{index}", stream_id=f"end:{index}")
    pruned_state = (pruned_memory.snapshot(), pruned_memory.learning_state())
    pruned_result = pruned_memory.generate(new_input, beam_width=1)

    embedded_memory = TrajectoryGenerationExperiment()
    embedded_source = embedded_memory.observe(cue, observation_id="embedded-cue",
                                              stream_id="first")
    embedded_memory.observe(target, observation_id="embedded-target", stream_id="first")
    unlinked_larger = wrapped(cue)
    embedded_memory.observe(unlinked_larger, observation_id="larger",
                            stream_id="second")
    nested_query = wrapped(unlinked_larger)
    embedded_state = (embedded_memory.snapshot(), embedded_memory.learning_state())
    nested_result = embedded_memory.generate(nested_query)
    closer_memory = TrajectoryGenerationExperiment.restore(embedded_state[0])
    closer_memory.observe(interposed, observation_id="larger-target", stream_id="second")
    closer_state = (closer_memory.snapshot(), closer_memory.learning_state())
    closer_result = closer_memory.embedded_root_relations(nested_query)
    closer_generated = closer_memory.generate(nested_query)
    closer_limited = closer_memory.generate(nested_query, beam_width=1)
    layered_memory = TrajectoryGenerationExperiment()
    layered_cue = wrapped(cue)
    for episode in range(2):
        layered_memory.observe(wrapped(layered_cue),
                               observation_id=f"layered-long:{episode}",
                               stream_id=f"layered-long:{episode}")
        layered_memory.observe(wrapped(target),
                               observation_id=f"layered-target:{episode}",
                               stream_id=f"layered-long:{episode}")
        layered_memory.observe(wrapped(cue),
                               observation_id=f"layered-short:{episode}",
                               stream_id=f"layered-short:{episode}")
        layered_memory.observe(wrapped(interposed),
                               observation_id=f"layered-other:{episode}",
                               stream_id=f"layered-short:{episode}")
    layered_query = wrapped(layered_cue)
    layered_state = (layered_memory.snapshot(), layered_memory.learning_state())
    layered_primary = layered_memory.associated_nodules(layered_query)
    layered_expanded = layered_memory.associated_nodules(
        layered_query, include_shorter=True,
    )
    layered_generated = layered_memory.generate(layered_query)
    layered_limited = layered_memory.generate(layered_query, beam_width=1)
    split_embedded = TrajectoryGenerationExperiment()
    split_embedded.observe(cue, observation_id="cue", stream_id="one")
    split_embedded.observe(target, observation_id="target", stream_id="two")
    split_embedded.observe(unlinked_larger, observation_id="larger", stream_id="three")

    # A known payload appears after a new cue in another capture. Its content
    # stays unique, but this previously unseen ordered pair is learned.
    reused_memory = TrajectoryGenerationExperiment()
    reused_memory.observe(target, observation_id="known-target", stream_id="archive")
    reused_source = wrapped(cue)
    reused_memory.observe(reused_source, observation_id="new-cue", stream_id="live")
    reused_query = wrapped(reused_source)
    reused_before = reused_memory.generate(reused_query)
    reused_content_count = reused_memory.learning_state()["learned_payloads"]
    reused_receipt = reused_memory.observe(target, observation_id="known-again",
                                           stream_id="live")
    reused_after = reused_memory.generate(reused_query)
    reused_link = reused_memory.temporal_neighbors(reused_source)
    reused_state = (reused_memory.snapshot(), reused_memory.learning_state())
    reused_memory.observe(reused_source, observation_id="another-cue",
                          stream_id="other")
    reused_same_pair = reused_memory.observe(target, observation_id="another-target",
                                             stream_id="other")
    reverse_memory = TrajectoryGenerationExperiment()
    reverse_memory.observe(target, observation_id="known", stream_id="archive")
    reverse_memory.observe(target, observation_id="earlier", stream_id="reverse")
    reverse_memory.observe(reused_source, observation_id="later", stream_id="reverse")

    memory.observe(new_input, observation_id="cue:2", stream_id="episode:2")
    before_interposition = memory.generate(new_input)
    prefix = memory.snapshot()

    same_target = TrajectoryGenerationExperiment.restore(prefix)
    same_target.observe(target, observation_id="target:2", stream_id="episode:2")
    converged = same_target.generate(new_input)

    split = TrajectoryGenerationExperiment.restore(prefix)
    split.observe(interposed, observation_id="split", stream_id="other")
    split_result = split.generate(new_input)

    memory.observe(interposed, observation_id="interposed:2", stream_id="episode:2")
    stored = memory.snapshot(), memory.learning_state()
    combined = memory.generate(new_input)
    limited = memory.generate(new_input, beam_width=1)
    read_only = (memory.snapshot(), memory.learning_state()) == stored
    for index in range(8):
        memory.observe(new_input, observation_id=f"copy:{index}",
                       stream_id=f"replay:{index}")
    replay_unchanged = (memory.learning_state() == stored[1] and
                        memory.generate(new_input) == combined)

    earlier_witnesses = (combined.association_evidence.candidates[0].witnesses
                         if combined.association_evidence else ())
    return dict(
        before_input_learns_from_prior_captures=(
            before_input.mode == "NODULE_RECALL" and before_input.selected == target),
        continuation_keeps_prior_route=(
            with_continuation.mode == "COMBINED_ROUTES"
            and tuple(candidate.output for candidate in with_continuation.candidates)
            == ((*new_input, continuation_tail), target)
            and with_continuation.ambiguous and with_continuation.selected is None
            and {stream for _, _, stream in continuation_witnesses}
            == {"episode:0", "episode:1"}),
        continuation_limit_refuses_to_select=(
            continuation_limited.truncated and continuation_limited.selected is None
            and continuation_limited.association_evidence is not None),
        continuation_is_read_only=continuation_read_only,
        continuation_duplicates_do_not_reinforce=continuation_duplicates_unchanged,
        continuation_reopen_matches=(
            TrajectoryGenerationExperiment.restore(continuation_state[0])
            .generate(new_input) == with_continuation),
        longer_cue_without_successor_keeps_shorter_route=(
            longer_association.selected == target
            and longer_result.mode == "COMBINED_ROUTES"
            and target in (candidate.output for candidate in longer_result.candidates)
            and longer_result.selected is None),
        pruned_end_keeps_root_successor=(
            pruned_result.mode == "COMBINED_ROUTES"
            and tuple(candidate.output for candidate in pruned_result.candidates)
            == (new_input,)
            and pruned_result.temporal_evidence[0].symbols == interposed
            and pruned_result.ambiguous and pruned_result.truncated
            and pruned_result.selected is None
            and (pruned_memory.snapshot(), pruned_memory.learning_state()) == pruned_state),
        unlinked_embedded_parent_keeps_child_route=(
            nested_result.mode == "EMBEDDED_TEMPORAL_RECALL"
            and nested_result.selected == target
            and nested_result.embedded_evidence.cue_payload_ids
            == (embedded_source.payload_id,)
            and nested_result.embedded_evidence.links[0].streams == ("first",)
            and (embedded_memory.snapshot(), embedded_memory.learning_state())
            == embedded_state),
        linked_embedded_parent_preserves_shorter_link=(
            tuple(neighbor.symbols for neighbor in closer_result.neighbors)
            == (interposed, target)
            and closer_result.cue_payload_ids[1] == embedded_source.payload_id
            and closer_generated.mode == "EMBEDDED_TEMPORAL_RECALL"
            and tuple(candidate.output for candidate in closer_generated.candidates)
            == (interposed, target)
            and closer_generated.ambiguous and closer_generated.selected is None
            and (closer_memory.snapshot(), closer_memory.learning_state()) == closer_state
            and TrajectoryGenerationExperiment.restore(closer_state[0])
            .generate(nested_query) == closer_generated),
        nested_limit_refuses_to_select=(
            tuple(candidate.output for candidate in closer_limited.candidates)
            == (interposed,) and closer_limited.truncated
            and closer_limited.selected is None),
        shorter_recurrent_route_blocks_apparent_unique=(
            layered_primary.selected == target
            and tuple(candidate.symbols for candidate in layered_expanded.candidates)
            == (target, interposed)
            and layered_generated.mode == "NODULE_RECALL"
            and tuple(candidate.output for candidate in layered_generated.candidates)
            == (target, interposed)
            and layered_generated.ambiguous and layered_generated.selected is None
            and (layered_memory.snapshot(), layered_memory.learning_state()) == layered_state
            and TrajectoryGenerationExperiment.restore(layered_state[0])
            .generate(layered_query) == layered_generated),
        shorter_recurrent_limit_refuses_to_select=(
            tuple(candidate.output for candidate in layered_limited.candidates)
            == (target,) and layered_limited.truncated
            and layered_limited.selected is None),
        split_embedded_capture_stays_unlinked=(
            split_embedded.generate(nested_query).mode == "ECHO"),
        reused_target_forms_new_pair_without_content_vote=(
            reused_before.mode == "ECHO"
            and not reused_receipt.learned and reused_receipt.new_relations == 1
            and reused_memory.learning_state()["learned_payloads"] == reused_content_count
            and reused_after.mode == "EMBEDDED_TEMPORAL_RECALL"
            and reused_after.selected == target
            and len(reused_link) == 1 and reused_link[0].symbols == target
            and reused_link[0].streams == ("live",)),
        reused_pair_does_not_reinforce=(
            reused_same_pair.new_relations == 0
            and reused_memory.learning_state() == reused_state[1]
            and reused_memory.generate(reused_query) == reused_after
            and TrajectoryGenerationExperiment.restore(reused_state[0])
            .generate(reused_query) == reused_after),
        reverse_reuse_does_not_create_forward_pair=(
            reverse_memory.temporal_neighbors(reused_source) == ()),
        after_input_before_interposition=(before_interposition.selected == target),
        unrelated_capture_does_not_create_exact_root_link=(
            split_result.mode == "NODULE_RECALL" and split_result.selected == target),
        interposed_exact_root_keeps_previous_target=(
            combined.mode == "COMBINED_RECALL"
            and tuple(candidate.output for candidate in combined.candidates)
            == (interposed, target)
            and combined.ambiguous and combined.selected is None
            and combined.temporal_evidence[0].streams == ("episode:2",)
            and {stream for _, _, stream in earlier_witnesses}
            == {"episode:0", "episode:1"}),
        limit_refuses_to_select=(limited.truncated and limited.selected is None
                                 and limited.association_evidence is not None),
        converged_target_is_single=(converged.mode == "COMBINED_RECALL"
                                    and len(converged.candidates) == 1
                                    and converged.selected == target),
        read_only=read_only,
        duplicate_did_not_reinforce=replay_unchanged,
        reopen_matches=(TrajectoryGenerationExperiment.restore(stored[0])
                        .generate(new_input) == combined),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--trials", type=int, default=12)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be positive")
    rng = Random(args.seed)
    rows = [trial(rng) for _ in range(args.trials)]
    counts = {name: sum(row[name] for row in rows) for name in rows[0]}
    passed = all(count == args.trials for count in counts.values())
    print(json.dumps(dict(format="memoria.ia-trajectory-online-probe-v1",
                          seed=args.seed, trials=args.trials,
                          result="PASS" if passed else "FAIL", counts=counts,
                          scope="opaque online trajectories; no factual answer claim"),
                     indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
