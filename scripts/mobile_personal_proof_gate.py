#!/usr/bin/env python3
"""Adversarial, synthetic no-LLM proof gate for personal memory retrieval.

The test data below is invented. It never reads or prints a private export.
Run with --strict to fail until all functional selection gates are satisfied.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from mobile_region_replay import NativeProbe


# (source_id, region, text, source_kind). A question deliberately carries the
# legacy user_assertion tag: the tag must never turn it into a fact by itself.
OBSERVATIONS = (
    ("answer-a", "answer-a", "Meu drone se chama Auri.", "user_turn"),
    ("echo-1", "echo-1", "Qual nome do meu drone?", "user_assertion"),
    ("echo-2", "echo-2", "Qual nome do meu drone?", "user_assertion"),
    ("echo-3", "echo-3", "Qual nome do meu drone?", "user_assertion"),
    ("near-echo", "near-echo", "Qual é o nome do meu drone?", "user_assertion"),
    ("other-answer", "other-answer", "Meu robô se chama Lumo.", "user_turn"),
    ("color", "color", "Meu drone é azul.", "user_turn"),
    ("motor-power", "motor-power", "A potência do meu motor é 30 watts.", "user_turn"),
    ("flight", "flight", "O meu drone voou perto do motor.", "user_turn"),
    ("generated", "answer-a", "Meu drone se chama Falso.", "assistant_generated"),
    ("answer-b", "answer-b", "Meu drone se chama Boreal.", "user_turn"),
)

QUERIES = {
    "known": "Qual nome do meu drone?",
    "other_subject": "Qual nome do meu robô?",
    # Every content token occurs somewhere, but no observation answers this.
    "absent_recombination": "Qual potência do meu drone?",
}

# The same question has two independent observed continuations, a competing
# third one and a repeated-question continuation. An assistant continuation
# must block traversal to the later user turn.
LINKED = (
    ("linked-q1", "linked-1", 1, QUERIES["known"], "user_turn"),
    ("linked-a1", "linked-1", 2, "Auri", "user_turn"),
    ("linked-q2", "linked-2", 1, QUERIES["known"], "user_turn"),
    ("linked-a2", "linked-2", 2, "Auri", "user_turn"),
    ("linked-q3", "linked-3", 1, QUERIES["known"], "user_turn"),
    ("linked-b", "linked-3", 2, "Boreal", "user_turn"),
    ("linked-q4", "linked-4", 1, QUERIES["known"], "user_turn"),
    ("linked-generated", "linked-4", 2, "Falso", "assistant_generated"),
    ("linked-after-generated", "linked-4", 3, "Auri", "user_turn"),
    ("linked-repeat-q1", "linked-repeat", 1, QUERIES["known"], "user_turn"),
    ("linked-repeat-q2", "linked-repeat", 2, QUERIES["known"], "user_turn"),
)


def resolve(probe: NativeProbe, query: str) -> dict:
    status, response = probe.call("resolve_structural_text", {
        "hierarchy_id": "conversation:new",
        "query": query,
        "mode": "personal_evidence",
        "top_k": 16,
    })
    if status != 2 or response.get("qualified") is True or response["status"] == "HIT":
        raise RuntimeError("personal evidence must not promote a factual HIT")
    return response


def region_rows(probe: NativeProbe, hierarchy_id: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    token = None
    while True:
        request = {"hierarchy_id": hierarchy_id, "offset": offset, "limit": 64}
        if token is not None:
            request["expected_token"] = token
        status, window = probe.call("read_structural_window", request)
        if status != 0:
            raise RuntimeError("addressable window read failed")
        token = window["window_token"]
        rows.extend(window["observations"])
        offset = window["page"]["next_offset"]
        if offset is None:
            return rows


def immediate_continuations(probe: NativeProbe, query: str) -> list[tuple[str, str]]:
    """Expose occurrence-local user successors, without calling them answers."""
    offset = 0
    witnesses: list[tuple[str, str]] = []
    windows: dict[str, list[dict]] = {}
    while True:
        status, page = probe.call("probe_structural_trails", {
            "query": query, "offset": offset, "limit": 64,
        })
        if status != 2 or page.get("qualified") is not False:
            raise RuntimeError("trail probe promoted an unqualified observation")
        for group in page["groups"]:
            if not group["query_echo"]:
                continue
            if group["sources_truncated"]:
                raise RuntimeError("query echo references truncated; cannot audit")
            for source in group["sources"]:
                region = source["hierarchy_id"]
                if region not in windows:
                    windows[region] = region_rows(probe, region)
                rows = windows[region]
                matching = [index for index, row in enumerate(rows)
                            if row["source_id"] == source["source_id"]
                            and row["sequence"] == source["sequence"]]
                if len(matching) != 1:
                    raise RuntimeError("echo source cannot be resolved uniquely")
                at = matching[0]
                if at + 1 >= len(rows):
                    continue
                next_row = rows[at + 1]
                if (next_row["sequence"] > source["sequence"] and
                    next_row["source_kind"] in ("user_turn", "user_assertion")):
                    witnesses.append((region, next_row["source_id"]))
        offset = page["page"]["next_offset"]
        if offset is None:
            return witnesses


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--strict", action="store_true",
                        help="exit with failure until all proof gates pass")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="memoria-personal-proof-") as directory:
        probe = NativeProbe(args.library, Path(directory))
        try:
            for index, (source_id, region, value, kind) in enumerate(OBSERVATIONS):
                if source_id == "answer-b":
                    break
                status, response = probe.call("observe_structural_text", {
                    "hierarchy_id": f"conversation:{region}",
                    "source_id": source_id,
                    "source_kind": kind,
                    "sequence": index + 1,
                    "text": value,
                })
                if status != 0 or response["duplicate"]:
                    raise RuntimeError("synthetic observation failed")

            baseline = {name: resolve(probe, query)
                        for name, query in QUERIES.items()}
            answer_ids = {row["source_id"] for row in baseline["known"]["contexts"]}
            gates = {
                "known_answer_addressable": "answer-a" in answer_ids,
                "known_answer_first": bool(baseline["known"]["contexts"])
                and baseline["known"]["contexts"][0]["source_id"] == "answer-a",
                "other_subject_first": bool(baseline["other_subject"]["contexts"])
                and baseline["other_subject"]["contexts"][0]["source_id"] == "other-answer",
                "absent_recombination_empty": not baseline["absent_recombination"]["contexts"],
                "assistant_output_excluded": all(
                    row["source_id"] != "generated"
                    for result in baseline.values() for row in result["contexts"]
                ),
            }

            last = OBSERVATIONS[-1]
            status, response = probe.call("observe_structural_text", {
                "hierarchy_id": f"conversation:{last[1]}",
                "source_id": last[0], "source_kind": last[3],
                "sequence": len(OBSERVATIONS), "text": last[2],
            })
            if status != 0 or response["duplicate"]:
                raise RuntimeError("conflicting synthetic observation failed")
            conflict = resolve(probe, QUERIES["known"])
            conflict_ids = {row["source_id"] for row in conflict["contexts"]}
            gates["competing_sources_visible"] = {"answer-a", "answer-b"} <= conflict_ids

            probe.reopen()
            cold = resolve(probe, QUERIES["known"])
            gates["cold_reopen_identical"] = cold == conflict
            expected = {source_id: (region, value, kind, index + 1)
                        for index, (source_id, region, value, kind)
                        in enumerate(OBSERVATIONS)}
            gates["cold_reopen_provenance"] = all(
                row["source_id"] in expected
                and row["source_text"] == expected[row["source_id"]][1]
                and row["source_hierarchy_id"] ==
                    f"conversation:{expected[row['source_id']][0]}"
                and probe.witness_exists(row["source_hierarchy_id"], row)
                for row in cold["contexts"]
            )
            for source_id, region, sequence, value, kind in LINKED:
                status, response = probe.call("observe_structural_text", {
                    "hierarchy_id": f"conversation:{region}",
                    "source_id": source_id, "source_kind": kind,
                    "sequence": sequence, "text": value,
                })
                if status != 0 or response["duplicate"]:
                    raise RuntimeError("linked synthetic observation failed")
            probe.reopen()
            continuations = immediate_continuations(probe, QUERIES["known"])
            gates["local_continuations_preserve_competition"] = {
                source_id for _, source_id in continuations
            } == {"linked-a1", "linked-a2", "linked-b", "linked-repeat-q2"}
            gates["assistant_turn_blocks_skip"] = all(
                source_id != "linked-after-generated"
                for _, source_id in continuations
            )
            gates["absent_query_has_no_continuation"] = not immediate_continuations(
                probe, QUERIES["absent_recombination"]
            )
            print(json.dumps({
                "observations": len(OBSERVATIONS) + len(LINKED),
                "functional_gates": gates,
                "occurrence_local_continuations": len(continuations),
                "cases": {
                    name: {
                        "status": result["status"],
                        "candidate_count": len(result["contexts"]),
                        "top_source_id": (
                            result["contexts"][0]["source_id"]
                            if result["contexts"] else None
                        ),
                    }
                    for name, result in baseline.items()
                },
            }, sort_keys=True))
        finally:
            probe.close()
    if args.strict and not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
