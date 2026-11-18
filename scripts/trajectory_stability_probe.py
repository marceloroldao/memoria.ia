#!/usr/bin/env python3
"""Probe recurrent route stability without supplying truth labels to memory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from random import Random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memoria_resolutiva.trajectory_generation_v2 import TrajectoryGenerationExperiment


def trial(rng: Random, index: int) -> dict[str, bool]:
    width = rng.randrange(2, 6)
    values = iter(rng.sample(range(10_000, 900_000), width * 4))
    cue, frequent, competing, isolated = (
        tuple(next(values) for _ in range(width)) for _ in range(4)
    )

    def wrapped(motif: tuple[int, ...]) -> tuple[int, ...]:
        return (rng.randrange(1_000_000, 2_000_000), *motif,
                rng.randrange(2_000_000, 3_000_000))

    memory = TrajectoryGenerationExperiment()
    sources: list[tuple[int, ...]] = []

    def route(label: str, target: tuple[int, ...], count: int) -> None:
        for occurrence in range(count):
            stream = f"{index}:{label}:{occurrence}"
            source = wrapped(cue)
            sources.append(source)
            memory.observe(source, observation_id=f"{stream}:source", stream_id=stream)
            memory.observe(wrapped(target), observation_id=f"{stream}:target", stream_id=stream)

    route("frequent", frequent, 4)
    route("competing", competing, 2)
    route("isolated", isolated, 1)
    query = wrapped(cue)
    baseline = memory.route_stability(query)
    generated = memory.generate(query)
    stored = memory.snapshot(), memory.learning_state()

    for copy in range(8):
        memory.observe(sources[0], observation_id=f"{index}:copy:{copy}",
                       stream_id=f"{index}:copy-stream:{copy}")
    duplicates_unchanged = (memory.learning_state() == stored[1]
                            and memory.route_stability(query) == baseline)

    new_stream = f"{index}:frequent:new"
    memory.observe(wrapped(cue), observation_id=f"{new_stream}:source",
                   stream_id=new_stream)
    memory.observe(wrapped(frequent), observation_id=f"{new_stream}:target",
                   stream_id=new_stream)
    reinforced = memory.route_stability(query)

    tie = TrajectoryGenerationExperiment()
    for label, target in (("left", frequent), ("right", competing)):
        for occurrence in range(2):
            stream = f"{index}:tie:{label}:{occurrence}"
            tie.observe(wrapped(cue), observation_id=f"{stream}:source", stream_id=stream)
            tie.observe(wrapped(target), observation_id=f"{stream}:target", stream_id=stream)
    tied = tie.route_stability(query)

    return dict(
        distinct_contexts_accumulate=(
            [candidate.witness_pairs for candidate in baseline.candidates] == [4, 2]
            and [len(candidate.independent_streams) for candidate in baseline.candidates]
            == [4, 2]),
        isolated_route_not_recurrent=(
            isolated not in {candidate.symbols for candidate in baseline.candidates}),
        stronger_route_is_measurable=(
            baseline.strongest == frequent
            and baseline.cross_stream_strongest == frequent
            and baseline.candidates[0].weight_share > baseline.candidates[1].weight_share),
        ambiguity_blocks_generation_selection=(
            baseline.ambiguous and generated.ambiguous and generated.selected is None),
        exact_duplicates_do_not_reinforce=duplicates_unchanged,
        new_context_increases_stability=(
            reinforced.candidates[0].witness_pairs == 5
            and reinforced.candidates[0].weight_share > baseline.candidates[0].weight_share),
        equal_routes_have_no_strongest=(tied.ambiguous and tied.strongest is None
                                        and tied.cross_stream_strongest is None),
        reopen_matches=(TrajectoryGenerationExperiment.restore(memory.snapshot())
                        .route_stability(query) == reinforced),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--trials", type=int, default=12)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be positive")
    rng = Random(args.seed)
    rows = [trial(rng, index) for index in range(args.trials)]
    counts = {name: sum(row[name] for row in rows) for name in rows[0]}
    passed = all(value == args.trials for value in counts.values())
    print(json.dumps(dict(format="memoria.ia-trajectory-stability-probe-v1",
                          seed=args.seed, trials=args.trials,
                          result="PASS" if passed else "FAIL", counts=counts,
                          scope="opaque recurrent routes; strongest is not factual selection"),
                     indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
