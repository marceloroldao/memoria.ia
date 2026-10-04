#!/usr/bin/env python3
"""Run the synthetic generative-trajectory proof gate without optional packages."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memoria_resolutiva.trajectory_generation_v2 import TrajectoryGenerationExperiment


def symbols(text):
    return tuple(map(ord, text))


def decode(values):
    return "".join(map(chr, values))


def demonstrate():
    memory = TrajectoryGenerationExperiment()
    bootstrap = []
    for i, text in enumerate(("oi", "hoje o dia está bonito", "hoje está quente")):
        result, _ = memory.respond(symbols(text), observation_id=f"bootstrap:{i}")
        bootstrap.append(dict(input=text, mode=result.mode, output=decode(result.selected)))

    generation = TrajectoryGenerationExperiment()
    generation.observe(symbols("hoje o dia está bonito"), observation_id="experience:1")
    result = generation.generate(symbols("amanhã o dia está "))

    packing = TrajectoryGenerationExperiment()
    nodule = packing.observe(symbols("qual nome do meu pai?"), observation_id="question")
    before = packing.learning_state()
    packing.observe(symbols("qual nome do meu pai?"), observation_id="copy")
    duplicate_did_not_learn = packing.learning_state() == before
    packing.observe(symbols("poderia me dizer qual nome do meu pai?"), observation_id="new-context")
    packed = packing.snapshot()["nodes"][1]["children"]

    branching = TrajectoryGenerationExperiment()
    branching.observe(symbols("hoje está bonito"), observation_id="one")
    branching.observe(symbols("hoje está quente"), observation_id="two")
    alternatives = branching.generate(symbols("hoje está "))

    composition = TrajectoryGenerationExperiment()
    for index, item in enumerate((
        (90, 1, 2, 3, 91), (94, 7, 8, 9, 95),
        (92, 1, 2, 3, 93), (96, 7, 8, 9, 97),
    )):
        composition.observe(item, observation_id=f"nodule:{index}")
    novel = (100, 1, 2, 3, 101)
    related = composition.associated_nodules(novel)

    text_memory = TrajectoryGenerationExperiment()
    for index, item in enumerate((
        "no quarto ensolarado", "a cama está arrumada",
        "este quarto é claro", "uma cama com cobertor",
    )):
        text_memory.observe(symbols(item), observation_id=f"room:{index}")
    room_query = "pensei no quarto durante a viagem!"
    room = text_memory.associated_nodules(symbols(room_query))
    return dict(
        bootstrap=bootstrap,
        deduplication=dict(
            duplicate_did_not_learn=duplicate_did_not_learn,
            payloads_stored=len(packing.snapshot()["nodes"]),
            occurrences=len(packing.snapshot()["observations"]),
            second_payload=[decode(tuple(x for x in packed if type(x) is int)),
                            "REFERENCE_TO_EXISTING_NODULE" if nodule.payload_id in packed else "MISSING_REFERENCE"],
        ),
        novel_continuation=dict(input="amanhã o dia está ", output=decode(result.selected),
                                mode=result.mode, generated_output_stored=any(
                                    generation.expand(node["address"]) == result.selected
                                    for node in generation.snapshot()["nodes"]
                                )),
        branching=dict(input="hoje está ", ambiguous=alternatives.ambiguous,
                       alternatives=[decode(c.output) for c in alternatives.candidates]),
        automatic_nodule_association=dict(
            cue_symbols=[1, 2, 3], related_symbols=list(related.selected),
            weight=round(related.candidates[0].weight, 6),
            witnessed_input_pairs=len(related.candidates[0].witnesses),
            generated_mode=composition.generate(novel).mode,
        ),
        text_adapter_association=dict(
            query=room_query, strongest_candidate=decode(room.candidates[0].symbols),
            competing_candidates=room.ambiguous, truncated=room.truncated,
            selected_output=decode(room.selected) if room.selected else None,
        ),
        scope="synthetic structural experiment; no claim of language understanding or mobile integration",
    )


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_trajectory_generation_v2.py")
    result = unittest.TextTestRunner(verbosity=2, stream=sys.stderr).run(suite)
    report = dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors))
    if result.wasSuccessful():
        report["demonstration"] = demonstrate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
