#!/usr/bin/env python3
"""Long occurrence sequences against cold replay and a pinned pre-change digest."""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memoria_resolutiva.trajectory_generation_v2 import GenerationConfig, TrajectoryGenerationExperiment


def normalize(value):
    if isinstance(value, float):
        return round(value, 12)  # Cross-platform digest only; cold parity below is exact.
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [normalize(item) for item in value]
    return value


def fixture(seed):
    rng = random.Random(seed)
    atoms = rng.sample(range(100, 1000000), 40)
    motifs = tuple(tuple(atoms[start:start + 3]) for start in (0, 3, 6))
    roots = tuple((atoms[9 + 2*i], *motif, atoms[10 + 2*i])
                  for i, motif in enumerate(motifs))
    memory = TrajectoryGenerationExperiment(GenerationConfig(forgetting_rate=0.02))
    for i, motif in enumerate(motifs):
        memory.observe((atoms[15 + 2*i], *motif, atoms[16 + 2*i]),
                       observation_id=f"pattern:{i}", stream_id=f"pattern:{i}")
        memory.observe(roots[i], observation_id=f"root:{i}", stream_id=f"root:{i}")
    queries = ((atoms[21], *motifs[0], atoms[22]),
               (atoms[23], *motifs[1], atoms[24]), roots[0])

    def read(instance):
        return tuple(tuple(asdict(result) for result in (
            instance.associated_nodules(query),
            instance.associated_nodules(query, channel="within"),
            instance.route_stability(query), instance.trace_nodule_paths(query),
            instance.generate(query),
        )) for query in queries)

    records = [read(memory)]  # Warm before updating any occurrence.
    updates = [(root, "active") for root in (roots[1], roots[2], roots[0], roots[1])]
    updates += [(roots[i % 2], "active") for i in range(48)]
    updates += [(root, "valid") for root in roots]
    updates += [((atoms[25], *motifs[2], atoms[26]), "novel")]
    updates += [(root, "novel") for root in roots]
    for index, (root, stream) in enumerate(updates):
        receipt = memory.observe(root, observation_id=f"occurrence:{index}", stream_id=stream)
        state, learned = memory.snapshot(), memory.learning_state()
        actual = read(memory)
        cold = TrajectoryGenerationExperiment.restore(state)
        assert read(cold) == actual, (seed, index, "full cold parity")
        assert read(memory) == actual, (seed, index, "warm read parity")
        assert (memory.snapshot(), memory.learning_state()) == (state, learned)
        records.append((asdict(receipt), actual))
    before = read(memory), memory.snapshot()
    memory.observe(updates[-1][0], observation_id=f"occurrence:{len(updates)-1}",
                   stream_id=updates[-1][1])
    assert (read(memory), memory.snapshot()) == before
    # Switch active hierarchy; the evicted projection must reconstruct exactly.
    memory.observe(roots[0], observation_id="other", hierarchy_id="other")
    memory.associated_nodules(queries[0], hierarchy_id="other")
    assert read(memory) == before[0]
    digest = sha256(json.dumps(normalize(records), sort_keys=True,
                               separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return dict(seed=seed, cycles=len(updates), digest=digest,
                exact_cold_parity=True, occurrence_witnesses_included=True)


def main():
    rows = [fixture(seed) for seed in (20260930, 20261003)]
    reference = json.loads((ROOT / "benchmark-results/trajectory-incremental-reference.json").read_text())
    assert [(row["seed"], row["digest"]) for row in rows] == [
        (row["seed"], row["digest"]) for row in reference["rows"]
    ], "pre-change trajectory digest mismatch"
    print(json.dumps(dict(rows=rows, reference_commit=reference["reference_commit"],
                         digest_float_decimals=12, pre_change_parity=True), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
