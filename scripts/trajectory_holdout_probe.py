#!/usr/bin/env python3
"""Prospective structural holdout probe with counterfactual controls.

The generator receives only opaque symbol sequences. Targets are retained by
this evaluator, never supplied to memory. No natural language truth claims.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from random import Random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memoria_resolutiva.trajectory_generation_v2 import TrajectoryGenerationExperiment


def patterns(rng: Random, *, count: int) -> tuple[tuple[int, ...], ...]:
    lengths = [rng.randrange(3, 7) for _ in range(count)]
    symbols = iter(rng.sample(range(10_000, 900_000), sum(lengths)))
    return tuple(tuple(next(symbols) for _ in range(length)) for length in lengths)


def encase(rng: Random, pattern: tuple[int, ...]) -> tuple[int, ...]:
    # Unique, arbitrary surroundings. Their IDs are from a different range
    # and convey no target label to the model.
    return (rng.randrange(1_000_000, 2_000_000), *pattern,
            rng.randrange(2_000_000, 3_000_000))


def train(events: list[tuple[int, ...]], *, streams: list[str] | None = None):
    memory = TrajectoryGenerationExperiment()
    for index, payload in enumerate(events):
        memory.observe(
            payload, observation_id=f"observed:{index}",
            stream_id="capture" if streams is None else streams[index],
        )
    return memory


def candidates(memory, query):
    return memory.associated_nodules(query)


def trial(rng: Random, index: int) -> dict[str, bool]:
    source, target, distractor, alternate = patterns(rng, count=4)
    source_events = [encase(rng, source) for _ in range(4)]
    target_events = [encase(rng, target) for _ in range(4)]
    distractor_events = [encase(rng, distractor) for _ in range(4)]
    alternate_events = [encase(rng, alternate) for _ in range(2)]
    query = (3_000_000 + index * 2, *source, 3_000_001 + index * 2)
    unrelated = (4_000_000 + index * 2, *patterns(rng, count=1)[0],
                 4_000_001 + index * 2)

    clean_events = [item for i in range(4)
                    for item in (source_events[i], target_events[i])]
    learned = train(clean_events)
    clean = candidates(learned, query)
    before = learned.learning_state()
    for copy in range(16):
        learned.observe(source_events[0], observation_id=f"duplicate:{copy}",
                        stream_id=f"replay:{copy}")
    unchanged = before == learned.learning_state() and clean == candidates(learned, query)

    reversed_events = list(target_events) + list(source_events)
    reversed_memory = train(reversed_events)
    split_memory = train(clean_events, streams=[
        "source" if position % 2 == 0 else "target"
        for position in range(len(clean_events))
    ])

    noisy_events = [item for i in range(4)
                    for item in (source_events[i], target_events[i], distractor_events[i])]
    noisy = candidates(train(noisy_events), query)

    competing_events = [
        item for i in range(4)
        for item in (source_events[i],
                     target_events[i] if i % 2 == 0 else alternate_events[i // 2])
    ]
    competing = candidates(train(competing_events), query)
    plain_target = next((item for item in clean.candidates if item.symbols == target), None)
    noisy_target = next((item for item in noisy.candidates if item.symbols == target), None)
    return {
        "clean_top1": bool(clean.candidates) and clean.candidates[0].symbols == target,
        "clean_in_top8": plain_target is not None,
        "query_was_novel": all(
            learned.expand(node["address"]) != query
            for node in learned.snapshot()["nodes"]
        ),
        "noisy_top1": bool(noisy.candidates) and noisy.candidates[0].symbols == target,
        "two_targets_retained": (
            {target, alternate}.issubset({item.symbols for item in competing.candidates})
            and competing.ambiguous and competing.selected is None
        ),
        "reversed_false_positive": bool(candidates(reversed_memory, query).candidates),
        "split_false_positive": bool(candidates(split_memory, query).candidates),
        "unrelated_false_positive": bool(candidates(learned, unrelated).candidates),
        "duplicate_changed_learning": not unchanged,
        "distractor_lowered_target_weight": (
            plain_target is not None and noisy_target is not None
            and noisy_target.weight < plain_target.weight
        ),
    }


def probe(*, seed: int, trials: int) -> dict:
    if trials < 1:
        raise ValueError("trials must be >= 1")
    rng = Random(seed)
    results = [trial(rng, index) for index in range(trials)]
    totals = {key: sum(int(row[key]) for row in results)
              for key in results[0]}
    # Acceptance is structural and intentionally modest; it is not a test of
    # semantics, truth, or independence of the synthetic training episodes.
    passed = (
        totals["clean_top1"] >= trials * 0.8
        and totals["clean_in_top8"] == trials
        and totals["query_was_novel"] == trials
        and totals["noisy_top1"] >= trials * 0.7
        and totals["two_targets_retained"] >= trials * 0.8
        and totals["distractor_lowered_target_weight"] >= trials * 0.8
        and all(totals[key] == 0 for key in (
            "reversed_false_positive", "split_false_positive",
            "unrelated_false_positive", "duplicate_changed_learning",
        ))
    )
    return {
        "format": "memoria.ia-trajectory-holdout-probe-v1",
        "seed": seed,
        "trials": trials,
        "result": "PASS" if passed else "FAIL",
        "counts": totals,
        "scope": "synthetic opaque sequences with held-out wrappers; no semantic or personal-fact accuracy claim",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260927)
    parser.add_argument("--trials", type=int, default=12)
    options = parser.parse_args()
    outcome = probe(seed=options.seed, trials=options.trials)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
