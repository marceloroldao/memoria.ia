#!/usr/bin/env python3
"""Observed question/content demonstrations, using the existing frame reader.

Opt-in research only: references never enter learning; questions are read-only.
Natural-text templates and injective Unicode renaming are correlated controls.
"""
import argparse
import copy
import json
from pathlib import Path
from random import Random
from string import ascii_lowercase, digits
import tempfile

from mobile_region_replay import NativeProbe
from trajectory_analogy_frame_probe import checked_read
from trajectory_native_evidence_join_probe import adapt_regions
from trajectory_region_evidence_probe import fingerprint
from trajectory_response_quality_probe import encode
from trajectory_window_consistency_probe import window_snapshot

FIELDS = ("hierarchy_id", "source_id", "sequence", "text", "source_kind")
CASES = ("three_examples", "no_examples", "two_examples", "repeated_one_example",
         "generated_example", "foreign_examples", "generated_target", "repeated_conflict",
         "crossed_examples", "unrelated_twin", "untrained_attribute_observed")


def read(rows, region, query, reader=checked_read):
    inputs = [{k: r[k] for k in FIELDS} for r in rows if r["hierarchy_id"] == region]
    memory, origins = adapt_regions(inputs)
    before = memory.snapshot(), memory.learning_state()
    view = reader(memory, encode(query, "unicode"))
    indexed = {(r["hierarchy_id"], r["source_id"], r["sequence"]): r for r in inputs}
    candidates = []
    for c in view["candidates"]:
        text = "".join(map(chr, c["output"]))
        addresses = origins[c["payload_id"]]
        if any(indexed[a]["text"] != text or indexed[a]["source_kind"] == "assistant_generated" for a in addresses):
            raise RuntimeError("unobserved frame payload or excluded source")
        candidates.append(dict(text=text, payload_id=c["payload_id"], origins=addresses,
                               frame_ids=c["frame_ids"], witnesses=c["witnesses"]))
    used_roots = {root for f in view["frames"] for pair in f["witnesses"] for root in pair[:2]}
    used_roots.update(c["payload_id"] for c in candidates)
    provenance = {root: dict(text="".join(map(chr, memory.expand(root))), origins=origins[root])
                  for root in sorted(used_roots)}
    if before != (memory.snapshot(), memory.learning_state()):
        raise RuntimeError("read changed learned memory")
    return dict(format="memoria.ia-question-frame-view-v1", region=region,
        frames=view["frames"], root_provenance=provenance, candidates=candidates, reason=view["reason"],
        proposal_payload_id=candidates[0]["payload_id"] if len(candidates) == 1 else None,
        answer=None, qualified=False, selected_target=None, selection_used=False,
        query_observed=False, factual_quality_status="NOT_EVALUATED")


def fixture(case, seed, renamed=False):
    if case not in CASES:
        raise ValueError("unknown case")
    region, foreign = f"conversation:question-{seed}", f"conversation:foreign-{seed}"
    rows = []
    def add(text, source, scope=region, kind="user_turn"):
        rows.append(dict(hierarchy_id=scope, source_id=source,
            sequence=1 + sum(r["hierarchy_id"] == scope for r in rows), text=text, source_kind=kind))
    subjects = ("barco", "avião", "sensor")
    relations = [("a cor", "A cor", ("azul", "preto", "cinza")),
                 ("o nome", "O nome", ("Atlas", "Íris", "Sol")),
                 ("a tensão", "A tensão", ("5 V", "9 V", "24 V"))]
    count = 0 if case == "no_examples" else 2 if case == "two_examples" else 3
    for relation, (source, target, values) in enumerate(relations):
        for i in range(count):
            j = 0 if case == "repeated_one_example" else i
            scope = foreign if case == "foreign_examples" else region
            question = f"Qual é {source} do {subjects[j]}?"
            answer_relation = 1 - relation if case == "crossed_examples" and relation < 2 else relation
            _, answer_prefix, answer_values = relations[answer_relation]
            answer = f"{answer_prefix} do {subjects[j]} é {answer_values[j]}."
            add(question, f"example-{relation}-{i}-question", scope)
            kind = "assistant_generated" if case == "generated_example" and relation == 0 and i == 2 else "user_turn"
            add(answer, f"example-{relation}-{i}-content", scope, kind)
            add("Intervalo observado.", f"example-{relation}-{i}-barrier", scope, "assistant_generated")
    texts = ["A cor do drone é verde.", "O nome do drone é Nova.", "A tensão do drone é 12 V."]
    for i, text in enumerate(texts):
        add(text, f"isolated-{i}", kind="assistant_generated" if case == "generated_target" and i == 0 else "user_turn")
        add("Intervalo observado.", f"isolated-{i}-barrier", kind="assistant_generated")
    if case == "repeated_conflict":
        for i in range(20):
            add(texts[0] if i else "A cor do drone é branca.", f"rival-copy-{i}")
            add("Intervalo observado.", f"rival-copy-{i}-barrier", kind="assistant_generated")
    age = "A idade do drone é 7 anos."
    if case == "untrained_attribute_observed":
        add(age, "isolated-age")
        add("Intervalo observado.", "isolated-age-barrier", kind="assistant_generated")
    color = [] if case == "generated_target" else [texts[0]]
    if case == "repeated_conflict":
        color += ["A cor do drone é branca."]
    queries = [dict(name="color", text="Qual é a cor do drone?", expected=color),
               dict(name="name", text="Qual é o nome do drone?", expected=[texts[1]]),
               dict(name="voltage", text="Qual é a tensão do drone?", expected=[texts[2]]),
               dict(name="age", text="Qual é a idade do drone?", expected=[age] if case == "untrained_attribute_observed" else []),
               dict(name="current_absent", text="Qual é a corrente do drone?", expected=[]),
               dict(name="entity_absent", text="Qual é a cor do foguete?", expected=[]),
               dict(name="paraphrase", text="Que cor tem o drone?", expected=color),
               dict(name="uppercase", text="QUAL É A COR DO DRONE?", expected=color),
               dict(name="added_prefix", text="Lembre: Qual é a cor do drone?", expected=color)]
    if case == "unrelated_twin":
        for query in queries:
            query["expected"] = []  # Evaluator-only hidden relevance; same inputs as the positive.
    if renamed:
        symbols = sorted({c for r in rows for c in r["text"]} | {c for q in queries for c in q["text"]})
        # Native text tokenization currently admits ASCII/Latin-1 word symbols.
        # Use an injective admitted alphabet, rather than changing that ABI.
        alphabet = list(ascii_lowercase + digits + "".join(chr(i) for i in range(0xE0, 0x100) if i != 0xF7))
        if len(symbols) > len(alphabet):
            raise ValueError("fixture exceeds admitted injective alphabet")
        Random(seed).shuffle(alphabet)
        mapping = dict(zip(symbols, alphabet))
        convert = lambda text: "".join(mapping[c] for c in text)
        rows = [dict(r, text=convert(r["text"])) for r in rows]
        queries = [dict(q, text=convert(q["text"]), expected=[convert(t) for t in q["expected"]]) for q in queries]
    return rows, region, queries


def persist(native, rows):
    for row in rows:
        stored = dict(row)
        if row["source_kind"] == "assistant_generated":
            stored["hierarchy_id"] += ":generated"
        status, value = native.call("observe_structural_text", stored)
        if status != 0 or value["duplicate"]:
            raise RuntimeError("native observation failed")


def collect(native, scopes):
    rows = []
    for scope in scopes:
        users = window_snapshot(native, scope)["rows"]
        generated = window_snapshot(native, scope + ":generated")["rows"]
        timeline = users + [dict(r, hierarchy_id=scope) for r in generated]
        rows += [{k:r[k] for k in FIELDS} for r in sorted(timeline, key=lambda r: (r["sequence"], r["source_id"]))]
    return rows


def score(texts, expected):
    actual, reference = set(texts), set(expected)
    return dict(exact_set=actual == reference, true_positive=len(actual & reference),
                false_positive=len(actual - reference), false_negative=len(reference - actual))


def trial(library, case, seed, renamed, fixture_factory=fixture, read_factory=read):
    rows, region, queries = fixture_factory(case, seed, renamed)
    scopes = list(dict.fromkeys(r["hierarchy_id"] for r in rows))
    with tempfile.TemporaryDirectory(prefix="memoria-question-frame-") as directory:
        native = NativeProbe(library, Path(directory))
        try:
            persist(native, rows)
            stored = collect(native, scopes)
            before = fingerprint(stored)
            outcomes, views, frames = [], [], None
            for query in queries:
                view = read_factory(stored, region, query["text"])
                views.append(view)
                if frames is None:
                    frames = view["frames"]
                elif frames != view["frames"]:
                    raise RuntimeError("query changed learned frames")
                status, legacy = native.call("resolve_structural_text", dict(hierarchy_id=region, query=query["text"], top_k=16))
                if status not in (0, 2):
                    raise RuntimeError("native recall failed")
                frame_texts = [c["text"] for c in view["candidates"]]
                legacy_texts = [c["source_text"] for c in legacy.get("contexts", [])]
                outcomes.append(dict(**query, frame_view={k:v for k,v in view.items() if k not in ("frames", "root_provenance")},
                    frame_score=score(frame_texts, query["expected"]),
                    native_texts=legacy_texts, native_score=score(legacy_texts, query["expected"])))
            checks = dict(native_rows_unchanged=before == fingerprint(collect(native, scopes)),
                input_projection_equal=stored == rows,
                held_out_queries_never_observed=all(q["text"] not in {r["text"] for r in stored if r["source_kind"] != "assistant_generated"} for q in queries),
                all_views_unqualified=all(v["answer"] is None and not v["qualified"] and not v["selection_used"] and v["selected_target"] is None for v in views),
                query_independent_frames=all(v["frames"] == frames for v in views))
            masked = [dict(r, reply_to={"source_id":"hidden"}, expected="evaluator", category="not-input") for r in stored]
            checks["metadata_masked"] = read_factory(masked, region, queries[0]["text"]) == views[0]
            native.reopen()
            cold = collect(native, scopes)
            checks["cold_rows_equal"] = cold == stored
            checks["cold_full_views_equal"] = all(read_factory(cold, region, q["text"]) == v for q, v in zip(queries, views))
            checks["origins_local_users"] = all(tuple(o) in {(r["hierarchy_id"],r["source_id"],r["sequence"]) for r in stored
                if r["hierarchy_id"] == region and r["source_kind"] == "user_turn"} for v in views for c in v["candidates"] for o in c["origins"])
            # Every observation root has immutable text/origins. Keep the union
            # once in the report, while cold parity still compares full views.
            provenance = {k:value for v in views for k,value in v["root_provenance"].items()}
            return dict(case=case, renamed=renamed, rows=stored, frames=frames,
                        root_provenance=provenance, checks=checks, queries=outcomes)
        finally:
            native.close()


def probe(library, seed):
    trials = [trial(library, case, seed, renamed) for renamed in (False, True) for case in CASES]
    checks = {f"{i}:{k}":v for i,t in enumerate(trials) for k,v in t["checks"].items()}
    for i,case in enumerate(CASES):
        plain, opaque = trials[i], trials[len(CASES)+i]
        checks["rename:"+case] = [q["frame_score"] for q in plain["queries"]] == [q["frame_score"] for q in opaque["queries"]]
    first, twin = trials[0], trials[CASES.index("unrelated_twin")]
    checks["hidden_reference_twin_same_rows"] = first["rows"] == twin["rows"]
    checks["hidden_reference_twin_same_views"] = [q["frame_view"] for q in first["queries"]] == [q["frame_view"] for q in twin["queries"]]
    totals = {}
    for route in ("frame", "native"):
        scores = [q[route+"_score"] for t in trials for q in t["queries"]]
        totals[route] = dict(queries=len(scores), exact_sets=sum(s["exact_set"] for s in scores),
            **{k:sum(s[k] for s in scores) for k in ("true_positive","false_positive","false_negative")})
    return dict(format="memoria.ia-question-frame-probe-v1", seed=seed,
        integrity_status="PASS" if all(checks.values()) else "FAIL", integrity_passed=sum(checks.values()),
        integrity_total=len(checks), checks=checks, totals=totals, cases=trials,
        retrieval_quality_status="PASS_CURATED_ONLY" if totals["frame"]["exact_sets"] == totals["frame"]["queries"] else "FAIL_EXTRA_OR_MISSING_CONTENT",
        hidden_relevance_status="FAIL_INDISTINGUISHABLE_INPUTS", factual_quality_status="NOT_EVALUATED",
        limitation="Literal learned text templates; curated correlated examples and symbol renaming, no general semantics or intention guarantee")


def summary(report):
    result = copy.deepcopy(report)
    result["full_report_sha256"] = fingerprint(report)
    for case in result["cases"]:
        for field in ("frames", "root_provenance"):
            value = case.pop(field)
            case[field + "_count"] = len(value)
            case[field + "_sha256"] = fingerprint(value)
        case["rows_sha256"] = fingerprint(case["rows"])
        for query in case["queries"]:
            for candidate in query["frame_view"]["candidates"]:
                witnesses = candidate.pop("witnesses")
                candidate["witness_count"] = len(witnesses)
                candidate["witnesses_sha256"] = fingerprint(witnesses)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261221)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary", action="store_true", help="Hash full frames/root provenance while retaining inputs, queries, candidates and failures")
    args = parser.parse_args()
    report = probe(args.library, args.seed)
    body = json.dumps(summary(report) if args.summary else report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    print(body, end="")
    raise SystemExit(0 if report["integrity_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
