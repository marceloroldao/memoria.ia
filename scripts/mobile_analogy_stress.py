#!/usr/bin/env python3
"""Falsify a structural analogy before using it for personal answers.

This read-only host experiment joins an observed query, its immediate user
continuation and another user payload containing that continuation. It then
projects the observed symbol positions to a new query. The returned rows are
unqualified candidates, never answers. Private runs print aggregate counts
only; the export and its contents remain local.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from collections import Counter
from pathlib import Path

from mobile_personal_proof_gate import LINKED, OBSERVATIONS, QUERIES
from mobile_region_replay import NativeProbe


# The native v1 tokenizer accepts precisely these character ranges and folds
# tokens before comparing them. This experiment does not persist its tokens.
TOKEN = re.compile(r"[A-Za-z0-9_À-ÿ]+")


def tokens(text: str) -> tuple[str, ...]:
    return tuple(match.group().casefold() for match in TOKEN.finditer(text))


def positions(haystack: tuple[str, ...], needle: tuple[str, ...]) -> list[int]:
    if not needle:
        return []
    return [index for index in range(len(haystack) - len(needle) + 1)
            if haystack[index:index + len(needle)] == needle]


def observed_exemplars(
    probe: NativeProbe, query: str, rows: list[dict],
) -> list[tuple[dict, dict, dict]]:
    by_source = {(row["hierarchy_id"], row["source_id"], row["sequence"]): row
                 for row in rows}
    offset = 0
    witnesses = []
    while True:
        status, page = probe.call("probe_structural_continuations", {
            "query": query, "offset": offset, "limit": 64,
        })
        if status != 2 or page["qualified"] is not False:
            raise RuntimeError("native continuation was qualified")
        witnesses.extend(page["witnesses"])
        offset = page["page"]["next_offset"]
        if offset is None:
            break
    exemplars = []
    for witness in witnesses:
        if witness["kind"] != "USER_CONTINUATION":
            continue
        region = witness["hierarchy_id"]
        echo = by_source[(region, witness["echo_source_id"],
                          witness["echo_sequence"])]
        successor = by_source[(region, witness["next"]["source_id"],
                               witness["next"]["sequence"])]
        q, r = tokens(echo["text"]), tokens(successor["text"])
        for assertion in rows:
            if (assertion is successor or
                assertion["source_kind"] not in ("user_turn", "user_assertion")):
                continue
            a = tokens(assertion["text"])
            if len(positions(a, r)) == 1 and set(q) & set(a):
                exemplars.append((echo, successor, assertion))
    return exemplars


def projected_candidates(
    exemplars: list[tuple[dict, dict, dict]], query: str, rows: list[dict],
) -> set[tuple[str, str, int]]:
    target = tokens(query)
    candidates = set()
    for echo, successor, assertion in exemplars:
        q, r, a = map(tokens, (
            echo["text"], successor["text"], assertion["text"],
        ))
        if len(q) != len(target):
            continue
        reply_at = positions(a, r)
        if len(reply_at) != 1:
            continue
        reply_slots = set(range(reply_at[0], reply_at[0] + len(r)))
        shared = [(i, j) for i, symbol in enumerate(q)
                  for j, other in enumerate(a)
                  if symbol == other and j not in reply_slots]
        changed = {i for i in range(len(q)) if q[i] != target[i]}
        if changed - {i for i, _ in shared}:
            continue
        allowed = reply_slots | {j for i, j in shared if i in changed}
        for candidate in rows:
            if candidate["source_kind"] not in ("user_turn", "user_assertion"):
                continue
            c = tokens(candidate["text"])
            if len(c) != len(a):
                continue
            if not changed and c[reply_at[0]:reply_at[0] + len(r)] != r:
                continue
            if any(c[j] != a[j] for j in range(len(a)) if j not in allowed):
                continue
            if any(c[j] != target[i] for i, j in shared if i in changed):
                continue
            candidates.add((candidate["hierarchy_id"],
                            candidate["source_id"], candidate["sequence"]))
    return candidates


def observe(probe: NativeProbe, rows: list[dict]) -> None:
    for row in rows:
        status, response = probe.call("observe_structural_text", row)
        if status != 0 or response["duplicate"]:
            raise RuntimeError("experimental observation failed")
    probe.reopen()


def synthetic_rows() -> list[dict]:
    rows = [
        {"hierarchy_id": f"conversation:{region}", "source_id": source_id,
         "source_kind": kind, "sequence": index + 1, "text": text}
        for index, (source_id, region, text, kind) in enumerate(OBSERVATIONS)
    ]
    rows.extend(
        {"hierarchy_id": f"conversation:{region}", "source_id": source_id,
         "source_kind": kind, "sequence": sequence, "text": text}
        for source_id, region, sequence, text, kind in LINKED
    )
    # This question has the same normalized trail as the actual assertion.
    # A purely structural projection cannot distinguish their epistemic roles.
    rows.append({
        "hierarchy_id": "conversation:decoy", "source_id": "question-decoy",
        "source_kind": "user_assertion", "sequence": 1,
        "text": "Meu robô se chama Lumo?",
    })
    return rows


def synthetic(library: Path) -> None:
    rows = synthetic_rows()
    with tempfile.TemporaryDirectory(prefix="memoria-analogy-synthetic-") as directory:
        probe = NativeProbe(library, Path(directory))
        try:
            observe(probe, rows)
            exemplars = observed_exemplars(probe, QUERIES["known"], rows)
            outcomes = {
                name: {source_id for _, source_id, _ in
                       projected_candidates(exemplars, query, rows)}
                for name, query in QUERIES.items()
            }
            if (outcomes["known"] != {"answer-a", "answer-b"} or
                outcomes["other_subject"] != {"other-answer", "question-decoy"} or
                outcomes["absent_recombination"]):
                raise RuntimeError("analogy stress fixture changed")
            synthetic_summary = {
                "exemplars": len(exemplars),
                "candidate_counts": {k: len(v) for k, v in outcomes.items()},
                "false_question_candidate": "question-decoy" in outcomes[
                    "other_subject"], "qualified": False,
            }
        finally:
            probe.close()
    names = {"drone": "sensor", "robô": "módulo", "nome": "código",
             "chama": "define", "potência": "carga", "motor": "circuito",
             "Auri": "Sigma", "Boreal": "Tau", "Lumo": "Iota"}

    def rename(text: str) -> str:
        for before, after in names.items():
            text = text.replace(before, after)
        return text

    renamed_rows = [dict(row, text=rename(row["text"])) for row in rows]
    with tempfile.TemporaryDirectory(prefix="memoria-analogy-renamed-") as directory:
        probe = NativeProbe(library, Path(directory))
        try:
            observe(probe, renamed_rows)
            exemplars = observed_exemplars(probe, rename(QUERIES["known"]),
                                            renamed_rows)
            renamed_outcomes = {
                name: {source_id for _, source_id, _ in
                       projected_candidates(exemplars, rename(query), renamed_rows)}
                for name, query in QUERIES.items()
            }
            if renamed_outcomes != outcomes:
                raise RuntimeError("analogy depends on fixture vocabulary")
        finally:
            probe.close()
    synthetic_summary["renaming_invariant"] = True
    print(json.dumps({"synthetic": synthetic_summary}, sort_keys=True))


def private(library: Path, export: Path, queries_path: Path | None) -> None:
    rows = json.loads(export.read_text(encoding="utf-8"))["structural"]["observations"]
    if queries_path:
        queries = json.loads(queries_path.read_text(encoding="utf-8"))
    else:
        queries = [text for text, _ in Counter(row["text"] for row in rows).most_common(4)]
    if not isinstance(queries, list) or not all(isinstance(q, str) and q for q in queries):
        raise ValueError("queries must be a JSON array of nonempty strings")
    with tempfile.TemporaryDirectory(prefix="memoria-analogy-private-") as directory:
        probe = NativeProbe(library, Path(directory))
        try:
            observe(probe, rows)
            aggregate = []
            for query in queries:
                exemplars = observed_exemplars(probe, query, rows)
                aggregate.append({"exemplars": len(exemplars),
                    "candidate_sources": len(projected_candidates(exemplars, query, rows))})
            print(json.dumps({"private_aggregate": aggregate}, sort_keys=True))
        finally:
            probe.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--queries", type=Path)
    args = parser.parse_args()
    if args.queries and not args.export:
        parser.error("--queries requires --export")
    synthetic(args.library)
    if args.export:
        private(args.library, args.export, args.queries)


if __name__ == "__main__":
    main()
