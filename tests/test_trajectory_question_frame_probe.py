import copy
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from trajectory_question_frame_probe import fixture, read, summary, trial


def views(case="three_examples", renamed=False):
    rows, region, queries = fixture(case, 20261221, renamed)
    return rows, region, queries, {q["name"]: read(rows, region, q["text"]) for q in queries}


def texts(view):
    return {c["text"] for c in view["candidates"]}


def test_demonstrations_separate_color_name_voltage_without_observing_new_queries():
    rows, _, queries, result = views()
    for q in queries[:3]:
        assert texts(result[q["name"]]) == set(q["expected"])
        assert result[q["name"]]["proposal_payload_id"] is not None
    assert all(q["text"] not in {r["text"] for r in rows} for q in queries)
    assert not texts(result["age"])
    assert not texts(result["current_absent"])
    assert not texts(result["entity_absent"])


def test_three_distinct_examples_are_needed_and_repeated_pair_cannot_replace_them():
    for case in ("no_examples", "two_examples", "repeated_one_example", "foreign_examples"):
        _, _, _, result = views(case)
        assert not texts(result["color"])
        assert not texts(result["name"])
        assert not texts(result["voltage"])


def test_repeated_conflict_retains_all_origins_without_majority_or_qualification():
    _, _, _, result = views("repeated_conflict")
    color = result["color"]
    assert texts(color) == {"A cor do drone é verde.", "A cor do drone é branca."}
    assert sorted(len(c["origins"]) for c in color["candidates"]) == [1, 20]
    assert color["proposal_payload_id"] is None
    assert color["answer"] is None and color["qualified"] is False
    assert color["selected_target"] is None and not color["selection_used"]


def test_generated_sources_never_supply_candidate_or_training_witness_origins():
    rows, _, _, result = views("generated_example")
    allowed = {(r["hierarchy_id"],r["source_id"],r["sequence"]) for r in rows if r["source_kind"] == "user_turn"}
    for v in result.values():
        assert all(tuple(o) in allowed for p in v["root_provenance"].values() for o in p["origins"])
        assert all(pair[0] in v["root_provenance"] and pair[1] in v["root_provenance"] for f in v["frames"] for pair in f["witnesses"])
    _, _, _, generated = views("generated_target")
    assert not texts(generated["color"])


def test_metadata_masking_and_query_read_leave_inputs_unchanged():
    rows, region, queries = fixture("three_examples", 20261221)
    before = copy.deepcopy(rows)
    original = read(rows, region, queries[0]["text"])
    assert rows == before
    changed = [dict(r, expected="hidden", reply_to={"source_id":"wrong"}, role="answer") for r in rows]
    assert read(changed, region, queries[0]["text"]) == original


def test_crossed_examples_and_hidden_relevance_twin_preserve_false_proposals():
    _, _, _, crossed = views("crossed_examples")
    assert texts(crossed["color"]) == {"O nome do drone é Nova."}
    _, _, _, positive = views()
    twin_rows, _, twin_queries, twin = views("unrelated_twin")
    assert positive == twin
    assert all(not q["expected"] for q in twin_queries)
    assert fixture("three_examples", 20261221)[0] == twin_rows


def test_paraphrase_uppercase_losses_and_untrained_literal_attribute_remain_explicit():
    _, _, _, result = views()
    assert not texts(result["paraphrase"])
    assert not texts(result["uppercase"])
    assert texts(result["added_prefix"]) == {"A cor do drone é verde."}
    _, _, _, extra = views("untrained_attribute_observed")
    assert texts(extra["age"]) == {"A idade do drone é 7 anos."}


@pytest.mark.skipif(not os.environ.get("MEMORIA_NATIVE_LIBRARY"), reason="requires native BDR library")
def test_native_cold_full_parity_and_opaque_symbol_control():
    library = Path(os.environ["MEMORIA_NATIVE_LIBRARY"])
    for renamed in (False, True):
        result = trial(library, "repeated_conflict", 20261221, renamed)
        assert all(result["checks"].values())
        assert result["queries"][0]["frame_score"]["exact_set"]
        report = dict(cases=[result])
        before = copy.deepcopy(report)
        compact = summary(report)
        assert report == before
        assert compact["full_report_sha256"]
        assert compact["cases"][0]["rows"] == result["rows"]
        assert compact["cases"][0]["queries"][0]["frame_score"] == result["queries"][0]["frame_score"]
