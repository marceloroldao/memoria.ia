#!/usr/bin/env python3
"""Replay a structural OFF.IA export without printing personal payloads.

The Python experiment only observes source text and capture order. Explicit
reply links are consulted afterward to evaluate retrieval, never to train it.
The tokenizer approximates the native v1 adapter; this is not an APK test.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memoria_resolutiva.trajectory_generation_v2 import (  # noqa: E402
    EmbeddedRootRecall,
    TrajectoryGenerationExperiment,
)


TOKEN = re.compile(r"[A-Za-z0-9_À-ÿ]+")
USER_SOURCES = {"user_assertion", "user_turn"}


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(match.group().casefold() for match in TOKEN.finditer(text))


def replay(document: dict) -> dict:
    """Return counts and verdicts only, without source text or identifiers."""
    structural = document.get("structural")
    rows = structural.get("observations") if isinstance(structural, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("expected nonempty structural observations")
    if any(not isinstance(row, dict) or
           not isinstance(row.get("text"), str) or
           not isinstance(row.get("hierarchy_id"), str) or
           not row["hierarchy_id"] or
           not isinstance(row.get("source_id"), str) or
           type(row.get("sequence")) is not int or
           row.get("source_kind") not in USER_SOURCES or
           not tokenize(row["text"]) for row in rows):
        raise ValueError("invalid user structural observation")

    # Preserve the export order, and require each capture's sequence to agree.
    first_stream = dict.fromkeys(row["hierarchy_id"] for row in rows)
    positions = [(row["hierarchy_id"], row["sequence"]) for row in rows]
    if len(set(positions)) != len(positions):
        raise ValueError("duplicate capture positions")
    previous_sequence: dict[str, int] = {}
    for row in rows:
        stream = row["hierarchy_id"]
        if row["sequence"] <= previous_sequence.get(stream, -1):
            raise ValueError("capture order does not match sequence")
        previous_sequence[stream] = row["sequence"]

    encoded_tokens = [tokenize(row["text"]) for row in rows]
    dictionary = {token: index for index, token in
                  enumerate(sorted(set().union(*encoded_tokens)))}
    payloads = [tuple(dictionary[token] for token in trail) for trail in encoded_tokens]
    sentinel = len(dictionary)
    memory = TrajectoryGenerationExperiment()
    learned = 0
    for index, (row, payload) in enumerate(zip(rows, payloads)):
        learned += memory.observe(
            payload, observation_id=f"row:{index}", stream_id=row["hierarchy_id"],
        ).learned

    frequencies = Counter(payloads)
    distinct = list(dict.fromkeys(payloads))
    repeated = [payload for payload in distinct if frequencies[payload] > 1]

    def query(payload: tuple[int, ...]) -> tuple[int, ...]:
        return (sentinel, *payload, sentinel + 1)

    outcomes = [memory.generate(query(payload)) for payload in distinct]
    repeated_outcomes = [memory.generate(query(payload)) for payload in repeated]
    by_mode = lambda results: dict(sorted(Counter(result.mode for result in results).items()))
    combined = [result for result in outcomes if result.mode == "COMBINED_RECALL"]
    combined_disjoint = sum(
        not ({candidate.symbols for candidate in result.association_evidence.candidates} &
             {neighbor.symbols for neighbor in result.embedded_evidence.neighbors})
        for result in combined
    )

    # reply_to provides evaluation labels only. We never pass them to observe.
    by_origin = {(row["hierarchy_id"], row["source_id"], row["sequence"]): index
                 for index, row in enumerate(rows)}
    linked = []
    resolved_pairs: list[tuple[int, int]] = []
    unresolved = 0
    for target_index, row in enumerate(rows):
        reference = row.get("reply_to")
        if not reference:
            continue
        if (not isinstance(reference, dict) or
            not isinstance(reference.get("source_id"), str) or
            type(reference.get("sequence")) is not int):
            raise ValueError("invalid reply reference")
        source_index = by_origin.get((row["hierarchy_id"],
                                      reference["source_id"], reference["sequence"]))
        if source_index is None or source_index >= target_index:
            unresolved += 1
            continue
        resolved_pairs.append((source_index, target_index))
        result = memory.generate(query(payloads[source_index]))
        prefix_result = memory.generate((sentinel, *payloads[source_index]))
        with patch.object(memory, "embedded_root_relations",
                          return_value=EmbeddedRootRecall((), (), (), False, False)):
            without_embedded = memory.generate(query(payloads[source_index]))
        target = payloads[target_index]
        linked.append(dict(
            without_embedded_mode=without_embedded.mode,
            with_embedded_mode=result.mode,
            target_in_candidates=target in (c.output for c in result.candidates),
            target_selected=result.selected == target,
            prefix_target_selected=prefix_result.selected == target,
            singleton_pair=(frequencies[payloads[source_index]] == 1 and
                            frequencies[target] == 1),
            ambiguous=result.ambiguous,
            truncated=result.truncated,
        ))

    # A second pass queries only the prefix already learned before each input.
    # Labels are used for aggregation after the calls, never in observe.
    online = TrajectoryGenerationExperiment()
    online_outcomes = []
    after_source = []
    before_target = []
    after_target = []

    def verdict(source: int, target: int) -> dict:
        result = online.generate(query(payloads[source]))
        return dict(mode=result.mode,
                    target_selected=result.selected == payloads[target],
                    target_in_candidates=payloads[target] in
                    (candidate.output for candidate in result.candidates),
                    ambiguous=result.ambiguous)

    for index, (row, payload) in enumerate(zip(rows, payloads)):
        online_outcomes.append(online.generate(payload))
        before_target.extend(verdict(source, target) for source, target in resolved_pairs
                             if target == index)
        online.observe(payload, observation_id=f"row:{index}",
                       stream_id=row["hierarchy_id"])
        after_source.extend(verdict(source, target) for source, target in resolved_pairs
                            if source == index)
        after_target.extend(verdict(source, target) for source, target in resolved_pairs
                            if target == index)

    return dict(
        observations=len(rows), captures=len(first_stream),
        distinct_payloads=len(distinct), exact_duplicate_occurrences=len(rows) - learned,
        distinct_repeated_payloads=len(repeated), opaque_symbol_addresses=len(dictionary),
        novel_wrapper=dict(
            unique_modes=by_mode(outcomes), repeated_modes=by_mode(repeated_outcomes),
            ambiguous=sum(result.ambiguous for result in outcomes),
            truncated=sum(result.truncated for result in outcomes),
            combined_disjoint_targets=combined_disjoint,
            combined_shared_targets=len(combined) - combined_disjoint,
            selected_non_echo=sum(result.selected is not None and result.mode != "ECHO"
                                  for result in outcomes),
        ),
        online_before_observe=dict(
            modes=by_mode(online_outcomes),
            ambiguous=sum(result.ambiguous for result in online_outcomes),
            truncated=sum(result.truncated for result in online_outcomes),
            selected_non_echo=sum(result.selected is not None and result.mode != "ECHO"
                                  for result in online_outcomes),
        ),
        chronological_reply_evaluation=dict(
            after_source_modes=dict(sorted(Counter(
                row["mode"] for row in after_source).items())),
            before_target_modes=dict(sorted(Counter(
                row["mode"] for row in before_target).items())),
            after_target_modes=dict(sorted(Counter(
                row["mode"] for row in after_target).items())),
            before_target_selected=sum(row["target_selected"] for row in before_target),
            after_target_selected=sum(row["target_selected"] for row in after_target),
            after_target_in_candidates=sum(row["target_in_candidates"] for row in after_target),
            after_target_ambiguous=sum(row["ambiguous"] for row in after_target),
        ),
        explicit_reply_evaluation=dict(
            total=sum(bool(row.get("reply_to")) for row in rows),
            resolved=len(linked), unresolved=unresolved,
            without_embedded_modes=dict(sorted(Counter(
                row["without_embedded_mode"] for row in linked).items())),
            with_embedded_modes=dict(sorted(Counter(
                row["with_embedded_mode"] for row in linked).items())),
            target_in_candidates=sum(row["target_in_candidates"] for row in linked),
            target_selected=sum(row["target_selected"] for row in linked),
            prefix_target_selected=sum(row["prefix_target_selected"] for row in linked),
            singleton_pairs=sum(row["singleton_pair"] for row in linked),
            ambiguous=sum(row["ambiguous"] for row in linked),
            truncated=sum(row["truncated"] for row in linked),
        ),
    )


def synthetic() -> dict:
    source = dict(hierarchy_id="capture", sequence=1, source_id="one",
                  source_kind="user_turn", text="alpha beta gamma")
    target = dict(hierarchy_id="capture", sequence=2, source_id="two",
                  source_kind="user_assertion", text="delta epsilon",
                  reply_to={"source_id": "one", "sequence": 1})
    duplicate = {**source, "hierarchy_id": "other", "source_id": "three"}
    result = replay({"structural": {"observations": [source, target, duplicate]}})
    if (result["exact_duplicate_occurrences"] != 1 or
        result["explicit_reply_evaluation"]["target_selected"] != 1 or
        result["chronological_reply_evaluation"]["before_target_selected"] != 0 or
        result["chronological_reply_evaluation"]["after_target_selected"] != 1 or
        result["explicit_reply_evaluation"]["without_embedded_modes"] != {"ECHO": 1}):
        raise AssertionError("synthetic embedded root replay failed")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, help="local OFF.IA JSON export")
    args = parser.parse_args()
    if args.export:
        result = replay(json.loads(args.export.read_text(encoding="utf-8")))
        print(json.dumps({"private_aggregate": result}, sort_keys=True))
    else:
        print(json.dumps({"synthetic": synthetic()}, sort_keys=True))


if __name__ == "__main__":
    main()
