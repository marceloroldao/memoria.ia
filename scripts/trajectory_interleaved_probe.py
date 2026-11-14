#!/usr/bin/env python3
"""Profile interleaved reads/observations and verify full cold-read parity."""
from __future__ import annotations

import argparse
import cProfile
from dataclasses import asdict
import json
from pathlib import Path
import pstats
import random
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memoria_resolutiva.trajectory_generation_v2 import (
    GenerationConfig, TrajectoryGenerationExperiment,
)


def read(memory, query):
    # asdict includes occurrence witnesses excluded from dataclass equality.
    return tuple(asdict(result) for result in (
        memory.associated_nodules(query), memory.route_stability(query),
        memory.trace_nodule_paths(query), memory.generate(query),
    ))


def run_case(seed, pairs, cycles, workload):
    rng = random.Random(seed)
    atoms = rng.sample(range(100, 10000000), 6 + pairs * 4 + cycles * 2 + 2)
    cue, target = tuple(atoms[:3]), tuple(atoms[3:6])
    memory = TrajectoryGenerationExperiment(GenerationConfig(forgetting_rate=0.01))
    roots = []
    for index in range(pairs):
        offset = 6 + index * 4
        roots.extend(((atoms[offset], *cue, atoms[offset + 1]),
                      (atoms[offset + 2], *target, atoms[offset + 3])))
        for kind, root in enumerate(roots[-2:]):
            memory.observe(root, observation_id=f"known:{index}:{kind}",
                           stream_id=f"archive:{index}")
    query = (atoms[-2], *cue, atoms[-1])
    read(memory, query)  # Warm before the measured interleaved cycle.
    initial = memory.snapshot()
    profiler = cProfile.Profile()
    observe_seconds = read_seconds = 0.0
    content_learned = new_root_relations = 0
    for cycle in range(cycles):
        if workload == "new_content":
            offset = 6 + pairs * 4 + cycle * 2
            payload = (atoms[offset], *(cue if cycle % 2 == 0 else target), atoms[offset + 1])
            observation, stream = f"new:{cycle}", "active"
        elif workload == "reused_new_pairs":
            payload = roots[cycle % len(roots)]
            observation, stream = f"reused:{cycle}", "active"
        elif workload == "reused_same_pair":
            payload = roots[cycle % 2]
            observation, stream = f"copy:{cycle}", "active"
        else:
            payload = roots[0]
            observation, stream = "known:0:0", "archive:0"
        profiler.enable()
        start = perf_counter()
        receipt = memory.observe(payload, observation_id=observation, stream_id=stream)
        observe_seconds += perf_counter() - start
        start = perf_counter()
        actual = read(memory, query)
        read_seconds += perf_counter() - start
        profiler.disable()
        content_learned += receipt.learned
        new_root_relations += receipt.new_relations
        state, learned = memory.snapshot(), memory.learning_state()
        oracle = TrajectoryGenerationExperiment.restore(state)
        assert read(oracle, query) == actual, (workload, pairs, cycle, "cold parity")
        assert read(memory, query) == actual, (workload, pairs, cycle, "warm parity")
        assert (memory.snapshot(), memory.learning_state()) == (state, learned)
    stats = pstats.Stats(profiler).stats

    def method_calls(filename, name):
        return sum(value[1] for (path, _, method), value in stats.items()
                   if path.endswith(filename) and method == name)

    builds = method_calls("compositional_association_v2.py", "__init__")
    catalogue_builds = method_calls("hierarchical_composition_v2.py", "build")
    assert builds == (cycles if workload == "new_content" else 0)
    assert catalogue_builds == (cycles if workload == "new_content" else 0)
    span_calls = method_calls("compositional_association_v2.py", "_project")
    if workload != "new_content":
        assert span_calls == 0
    if workload == "idempotent_id":
        assert memory.snapshot() == initial
    else:
        assert len(memory.snapshot()["observations"]) == len(initial["observations"]) + cycles
    assert content_learned == (cycles if workload == "new_content" else 0)
    hotspots = sorted(stats.items(), key=lambda item: item[1][2], reverse=True)[:6]
    return dict(
        initial_payloads=len(initial["nodes"]), cycles=cycles, workload=workload,
        content_learned=content_learned, new_root_relations=new_root_relations,
        projection_builds=builds,
        catalogue_builds=catalogue_builds,
        span_projection_calls=span_calls,
        profiled_observe_seconds=round(observe_seconds, 6),
        profiled_read_seconds=round(read_seconds, 6),
        cold_and_warm_parity=True, includes_occurrence_witnesses=True,
        hotspots=[dict(file=Path(key[0]).name, function=key[2], calls=value[1],
                       self_seconds=round(value[2], 6)) for key, value in hotspots],
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--cycles", type=int, default=8)
    args = parser.parse_args()
    if not 4 <= args.cycles <= 32:
        parser.error("cycles must be between 4 and 32")
    rows = [run_case(args.seed + pairs, pairs, args.cycles, workload)
            for pairs in (8, 24, 64)
            for workload in ("new_content", "reused_new_pairs", "reused_same_pair", "idempotent_id")]
    print(json.dumps(dict(seed=args.seed, rows=rows,
                         scope="synthetic Python interleaved profiling; not production, Android or RAM",
                         timing_includes_profiler=True), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
