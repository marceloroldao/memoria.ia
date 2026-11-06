#!/usr/bin/env python3
"""Synthetic warm/cold read projection parity; timings are descriptive only."""
from __future__ import annotations

import json
from pathlib import Path
import random
import sys
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memoria_resolutiva.compositional_association_v2 import CompositionalAssociationView
from memoria_resolutiva.trajectory_generation_v2 import TrajectoryGenerationExperiment


def main():
    rng = random.Random(20260930)
    addresses = rng.sample(range(100, 1000000), 108)
    cue, target = tuple(addresses[:3]), tuple(addresses[3:6])
    memory = TrajectoryGenerationExperiment()
    for index in range(24):
        offset = 6 + index * 4
        memory.observe((addresses[offset], *cue, addresses[offset + 1]),
                       observation_id=f"cue:{index}", stream_id=f"capture:{index}")
        memory.observe((addresses[offset + 2], *target, addresses[offset + 3]),
                       observation_id=f"target:{index}", stream_id=f"capture:{index}")
    query = (addresses[-2], *cue, addresses[-1])
    snapshot, learned = memory.snapshot(), memory.learning_state()

    def read():
        return (memory.associated_nodules(query), memory.route_stability(query),
                memory.trace_nodule_paths(query), memory.generate(query))

    memory._compositional_views.clear()  # Discard derived data, never learning state.
    with patch("memoria_resolutiva.trajectory_generation_v2.CompositionalAssociationView",
               wraps=CompositionalAssociationView) as rebuild:
        start = perf_counter()
        expected = read()
        for _ in range(9):
            assert read() == expected
        warm_seconds = perf_counter() - start
        warm_builds = rebuild.call_count
    with patch("memoria_resolutiva.trajectory_generation_v2.CompositionalAssociationView",
               wraps=CompositionalAssociationView) as rebuild:
        start = perf_counter()
        for _ in range(10):
            memory._compositional_views.clear()
            assert read() == expected
        cold_seconds = perf_counter() - start
        cold_builds = rebuild.call_count
    assert warm_builds == 1 and cold_builds == 10
    assert (memory.snapshot(), memory.learning_state()) == (snapshot, learned)
    assert TrajectoryGenerationExperiment.restore(snapshot).generate(query) == expected[-1]
    print(json.dumps(dict(
        observations=len(snapshot["observations"]), read_batches=10,
        cold_projection_builds=cold_builds, reused_projection_builds=warm_builds,
        cold_seconds=round(cold_seconds, 6), reused_seconds=round(warm_seconds, 6),
        parity=True, learning_state_unchanged=True,
        scope="synthetic repeated reads; not a mobile, production or RAM benchmark",
    ), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
