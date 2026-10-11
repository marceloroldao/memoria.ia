#!/usr/bin/env python3
"""Synthetic response quality: evaluation labels never enter the memory engine."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from random import Random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memoria_resolutiva.trajectory_generation_v2 import TrajectoryGenerationExperiment


def encode(text, adapter):
    return tuple(map(ord, text)) if adapter == "unicode" else tuple(text.encode("utf-8"))


def decode(symbols, adapter):
    if adapter == "unicode":
        return "".join(map(chr, symbols)), True
    try:
        return bytes(symbols).decode("utf-8"), True
    except UnicodeDecodeError:
        return bytes(symbols).decode("utf-8", errors="replace"), False


def question(name):
    return f"Código de {name}?"


def answer(name, code):
    return f"{name}: {code}."


def fixture_groups(rng):
    first, second, absent = rng.sample(("Luma", "Neri", "Vero", "Daro", "Kivo", "Zuri"), 3)
    value, other, conflicting = rng.sample(range(100, 999), 3)
    q, a = question(first), answer(first, value)
    q2, a2 = question(second), answer(second, other)
    conflict = answer(first, conflicting)
    unrelated = "Temperatura de Marte?"

    def case(name, query, expected=(), kind="answer", required=True):
        return dict(name=name, query=query, expected=expected, kind=kind, required=required)

    def records(pairs):
        return [(text, f"capture:{i}") for i, pair in enumerate(pairs) for text in pair]

    return [
        ("exact", records([(q, a)]), [
            case("known_query", q, (a,)),
            case("new_prefix", "Lembre: " + q, (a,)),
            case("case_change", q.lower(), (a,), required=False),
            case("unknown_subject", question(absent), kind="absence"),
            case("unrelated", unrelated, kind="absence"),
        ]),
        ("wrapped", records([(f"r{i}: {q}", f"r{i}: {a}")
                             for i in range(3)]), [
            case("new_surface", q, (a,)),
            case("new_prefix", "Lembre: " + q, (a,)),
            case("unknown_subject", question(absent), kind="absence"),
        ]),
        ("two_subjects", records([(f"r{i}: {query}", f"r{i}: {reply}")
                                  for i in range(2) for query, reply in ((q, a), (q2, a2))]), [
            case("first_subject", q, (a,)),
            case("second_subject", q2, (a2,)),
            case("absent_third", question(absent), kind="absence"),
        ]),
        ("conflict", records([(q, a), (q, conflict)]), [
            case("competing_replies", q, (a, conflict), kind="conflict"),
        ]),
        ("question_only", [(q, "capture")], [
            case("no_observed_reply", q, kind="absence"),
        ]),
        ("split_capture", [(q, "question-capture"), (a, "answer-capture")], [
            case("no_ordered_pair", q, kind="absence"),
        ]),
    ]


def evaluate_case(memory, reopened, descriptor, adapter):
    query = encode(descriptor["query"], adapter)
    before = memory.snapshot(), memory.learning_state()
    result = memory.generate(query)  # Production defaults of the experimental generator.
    assert asdict(result) == asdict(reopened.generate(query)), "cold result changed"
    assert (memory.snapshot(), memory.learning_state()) == before, "query learned"
    outputs = [decode(candidate.output, adapter) for candidate in result.candidates]
    selected = None if result.selected is None else decode(result.selected, adapter)
    # Echo is the bootstrap/absence behavior, not an answer to the query.
    responsive = result.mode != "ECHO" and selected is not None
    expected = descriptor["expected"]
    retained = [any(reply in text for text, valid in outputs if valid) for reply in expected]
    selected_correct = bool(responsive and selected[1] and len(expected) == 1
                            and expected[0] in selected[0])
    false_unique = bool(responsive and not selected_correct and descriptor["kind"] != "conflict")
    if descriptor["kind"] == "answer":
        quality = selected_correct
    elif descriptor["kind"] == "absence":
        quality = not responsive
    else:
        quality = not responsive and all(retained)
    return dict(
        **descriptor, adapter=adapter, mode=result.mode,
        outputs=[text for text, _ in outputs],
        selected=None if selected is None else selected[0],
        invalid_output_count=sum(not valid for _, valid in outputs),
        ambiguous=result.ambiguous, truncated=result.truncated,
        targets_retained=retained, selected_correct=selected_correct,
        false_unique=false_unique, quality_pass=quality,
        read_only=True, cold_parity=True,
    )


def probe(seed, trials):
    rng = Random(seed)
    cases = []
    for trial in range(trials):
        groups = fixture_groups(rng)
        for adapter in ("unicode", "utf8"):
            for group, records, descriptors in groups:
                memory = TrajectoryGenerationExperiment()
                for index, (text, stream) in enumerate(records):
                    memory.observe(encode(text, adapter), observation_id=f"input:{index}",
                                   stream_id=stream)
                reopened = TrajectoryGenerationExperiment.restore(memory.snapshot())
                for descriptor in descriptors:
                    row = evaluate_case(memory, reopened, descriptor, adapter)
                    row.update(trial=trial, group=group)
                    cases.append(row)
    required = [row for row in cases if row["required"]]
    counts = Counter()
    for row in cases:
        counts[f"{row['kind']}_cases"] += 1
        counts["correct_unique_answers"] += row["selected_correct"]
        counts["false_unique_outputs"] += row["false_unique"]
        counts["answer_targets_retained"] += row["kind"] == "answer" and all(row["targets_retained"])
        counts["absence_abstentions"] += row["kind"] == "absence" and row["quality_pass"]
        counts["conflicts_preserved"] += row["kind"] == "conflict" and row["quality_pass"]
        counts["invalid_outputs"] += row["invalid_output_count"]
    return dict(
        format="memoria.ia-response-quality-synthetic-v1", seed=seed, trials=trials,
        integrity_status="PASS", quality_status="PASS" if all(row["quality_pass"] for row in required) else "FAIL",
        counts=dict(counts), required_cases=len(required),
        required_passes=sum(row["quality_pass"] for row in required),
        cases=cases,
        scope="fictional text fixtures, raw Unicode/UTF-8 adapters; no personal or multimodal accuracy claim",
        labels_used_by_engine=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--strict-quality", action="store_true")
    options = parser.parse_args()
    if not 1 <= options.trials <= 8:
        parser.error("trials must be between 1 and 8")
    report = probe(options.seed, options.trials)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if options.strict_quality and report["quality_status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
