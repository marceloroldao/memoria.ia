#!/usr/bin/env python3
"""Cross-capture structural episode probe; no answer labels enter memory."""
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
    lengths = (2, rng.randrange(3, 6), rng.randrange(3, 6),
               rng.randrange(3, 6), rng.randrange(3, 6))
    values = iter(rng.sample(range(10_000, 900_000), sum(lengths) + lengths[3]))

    def take(size: int) -> tuple[int, ...]:
        return tuple(next(values) for _ in range(size))

    shared, tail_a, tail_b, target_a, target_b = (take(size) for size in lengths)
    distractor = take(len(target_a))
    source_a, source_b = shared + tail_a, shared + tail_b

    def wrapped(motif: tuple[int, ...]) -> tuple[int, ...]:
        return (rng.randrange(1_000_000, 2_000_000), *motif,
                rng.randrange(2_000_000, 3_000_000))

    episodes = [
        (f"{kind}:{episode}", wrapped(source), wrapped(target))
        for episode in range(4)
        for kind, source, target in (
            ("a", source_a, target_a), ("b", source_b, target_b)
        )
    ]
    query_a = (3_000_000 + index * 8, *source_a, 3_000_001 + index * 8)
    query_b = (3_000_002 + index * 8, *source_b, 3_000_003 + index * 8)
    query_shared = (3_000_004 + index * 8, *shared, 3_000_005 + index * 8)
    unrelated = (3_000_006 + index * 8, *take_unused(rng), 3_000_007 + index * 8)

    def learn(mode: str) -> TrajectoryGenerationExperiment:
        memory = TrajectoryGenerationExperiment()
        for episode, (stream, source, target) in enumerate(episodes):
            if mode == "reverse":
                events = ((stream, target), (stream, source))
            elif mode == "split":
                events = ((stream + ":source", source), (stream + ":target", target))
            elif mode == "interposed" and stream.startswith("a:"):
                # A second recurring cue between A and its target has no
                # externally supplied role; both temporal links are real.
                sibling = (5_000_000 + index * 100 + episode, *source_b,
                           6_000_000 + index * 100 + episode)
                events = ((stream, source), (stream, sibling), (stream, target))
            else:
                events = ((stream, source), (stream, target))
                if mode == "distractor" and stream.startswith("a:"):
                    events += ((stream, wrapped(distractor)),)
            for position, (scope, payload) in enumerate(events):
                memory.observe(payload, observation_id=f"{episode}:{position}",
                               stream_id=scope)
        return memory

    memory = learn("clean")
    state = memory.learning_state()
    stored = memory.snapshot()
    a = memory.associated_nodules(query_a)
    b = memory.associated_nodules(query_b)
    common = memory.associated_nodules(query_shared)
    generated = memory.generate(query_a)
    read_only = (memory.learning_state() == state and memory.snapshot() == stored)
    before_replay = a
    for copy in range(16):
        memory.observe(episodes[0][1], observation_id=f"duplicate:{copy}",
                       stream_id=f"new-capture:{copy}")
    exact_replay_unchanged = (memory.learning_state() == state
                              and memory.associated_nodules(query_a) == before_replay)
    reversed_memory = learn("reverse")
    split_memory = learn("split")
    noisy_a = learn("distractor").associated_nodules(query_a)
    interposed = learn("interposed")
    interposed_a = interposed.associated_nodules(query_a)
    interposed_b = interposed.associated_nodules(query_b)
    target = next((candidate for candidate in a.candidates
                   if candidate.symbols == target_a), None)
    noisy_target = next((candidate for candidate in noisy_a.candidates
                         if candidate.symbols == target_a), None)
    noisy_distractor = next((candidate for candidate in noisy_a.candidates
                             if candidate.symbols == distractor), None)
    return {
        "specific_a": {c.symbols for c in a.candidates} == {target_a} and a.selected == target_a,
        "specific_b": {c.symbols for c in b.candidates} == {target_b} and b.selected == target_b,
        "novel_queries": all(
            all(memory.expand(node["address"]) != query for node in stored["nodes"])
            for query in (query_a, query_b, query_shared)
        ),
        "shared_cue_ambiguous": ({c.symbols for c in common.candidates} ==
                                 {target_a, target_b} and common.ambiguous
                                 and common.selected is None),
        "four_independent_witnesses": (
            target is not None and len(target.witnesses) == 4
            and {stream for _, _, stream in target.witnesses}
            == {f"a:{episode}" for episode in range(4)}
        ),
        "generated_from_nodule": (generated.mode == "NODULE_RECALL"
                                  and generated.selected == target_a and read_only),
        "distractor_ambiguous": (
            noisy_target is not None and noisy_distractor is not None
            and noisy_target.weight > noisy_distractor.weight
            and target_b not in {candidate.symbols for candidate in noisy_a.candidates}
            and noisy_a.ambiguous and noisy_a.selected is None
        ),
        "interposed_targets_visible": (
            target_a in {c.symbols for c in interposed_a.candidates}
            and target_b in {c.symbols for c in interposed_b.candidates}
        ),
        "interposed_refuses_single_answer": (
            interposed_a.ambiguous and interposed_a.selected is None
            and interposed_b.ambiguous and interposed_b.selected is None
        ),
        # Report-only limits: proximity alone cannot distinguish the sibling
        # cue from an answer, or choose B's target when B appears in A's stream.
        "interposed_sibling_first": (
            bool(interposed_a.candidates)
            and interposed_a.candidates[0].symbols == source_b
        ),
        "interposed_cross_target": (
            target_a in {c.symbols for c in interposed_b.candidates}
        ),
        "reverse_false_positive": any(
            reversed_memory.associated_nodules(query).candidates
            for query in (query_a, query_b)
        ),
        "split_false_positive": any(
            split_memory.associated_nodules(query).candidates
            for query in (query_a, query_b)
        ),
        "unrelated_false_positive": bool(memory.associated_nodules(unrelated).candidates),
        "exact_replay_changed_learning": not exact_replay_unchanged,
    }


def take_unused(rng: Random) -> tuple[int, ...]:
    # Disjoint range from all learned motif and wrapper symbols.
    return tuple(rng.sample(range(4_000_000, 5_000_000), 4))


def probe(*, seed: int, trials: int) -> dict:
    if trials < 1:
        raise ValueError("trials must be >= 1")
    rng = Random(seed)
    results = [trial(rng, index) for index in range(trials)]
    totals = {key: sum(int(row[key]) for row in results) for key in results[0]}
    positives = ("specific_a", "specific_b", "novel_queries", "shared_cue_ambiguous",
                 "four_independent_witnesses", "generated_from_nodule",
                 "distractor_ambiguous", "interposed_targets_visible",
                 "interposed_refuses_single_answer")
    negatives = ("reverse_false_positive", "split_false_positive",
                 "unrelated_false_positive", "exact_replay_changed_learning")
    passed = (all(totals[key] == trials for key in positives)
              and all(totals[key] == 0 for key in negatives))
    return {
        "format": "memoria.ia-trajectory-episode-probe-v1",
        "seed": seed, "trials": trials,
        "result": "PASS" if passed else "FAIL",
        "counts": totals,
        "scope": "synthetic opaque multi-capture episodes; structural recall only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260928)
    parser.add_argument("--trials", type=int, default=12)
    args = parser.parse_args()
    result = probe(seed=args.seed, trials=args.trials)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
