#!/usr/bin/env python3
"""Online adversarial probe for exact-root and recurrent-nodule competition."""
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
