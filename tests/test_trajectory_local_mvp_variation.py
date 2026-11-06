import copy
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from trajectory_local_mvp_variation_gate import evaluate, fixture, gate, threshold_shadow


def sample():
    recorded = [dict(hierarchy_id="conversation:mvp:demo", source_id=f"s{i}", sequence=i,
                     text="Observed A", source_kind="user_turn") for i in (1, 2)]
    view = dict(query_recorded=False, answer=None, qualified=False, selected_target=None,
        selection_used=False, status="CANDIDATES", retrieval={}, candidates=[dict(
            text="Observed A", origins=[{k: r[k] for k in ("hierarchy_id", "source_id", "sequence", "source_kind")} for r in recorded],
            native_support={"score": 0.99}, support_is_factual_confidence=False,
            evidence_kind="NATIVE_STRUCTURAL_RECALL")])
    spec = dict(scope="demo", name="case", query="Question", category="positive", expected=["Observed A"])
    return spec, view, recorded


def test_evaluator_reference_change_does_not_change_or_promote_memory_output():
    spec, view, recorded = sample()
    before = copy.deepcopy(view)
    assert evaluate(spec, view, recorded)["exact_retrieval_set"]
    spec["expected"] = []
    result = evaluate(spec, view, recorded)
    assert result["false_positive"] == 1
    assert result["false_negative"] == 0
    assert not result["exact_retrieval_set"]
    assert view == before


def test_source_loss_generated_origin_and_unobserved_source_are_detected():
    spec, view, recorded = sample()
    view["candidates"][0]["origins"].pop()
    assert not evaluate(spec, view, recorded)["checks"]["complete_payload_origins"]
    view["candidates"][0]["origins"][0]["source_id"] = "nonexistent"
    assert not evaluate(spec, view, recorded)["checks"]["observed_origins"]
    view["candidates"][0]["origins"][0]["source_kind"] = "assistant_generated"
    assert not evaluate(spec, view, recorded)["checks"]["generated_excluded"]


def test_catalog_keeps_correlated_questions_and_absence_references_separate():
    entries, cases = fixture()
    assert len(cases) == 37
    assert len({(c["scope"], c["name"]) for c in cases}) == len(cases)
    assert sum(c["category"] == "absent_attribute" for c in cases) == 10
    assert sum(c["category"] == "conflict" for c in cases) == 7
    assert all(set(e) == {"scope", "text", "source_kind"} for e in entries)
    assert any(e["source_kind"] == "assistant_generated" for e in entries)


def test_score_shadow_keeps_fixed_input_and_does_not_install_a_threshold():
    spec, view, recorded = sample()
    positive = evaluate(spec, view, recorded)
    negative = evaluate(dict(spec, expected=[]), view, recorded)
    cases = [positive, negative]
    before = copy.deepcopy(cases)
    report = threshold_shadow(cases)
    assert not report["exact_all_cases_possible"]
    assert report["most_reference_content_without_extra"] == 0
    assert report["least_extra_with_all_reference_content"] == 1
    assert report["selection_used"] is False
    assert report["calibrated_confidence"] is False
    assert cases == before


@pytest.mark.skipif(not os.environ.get("MEMORIA_NATIVE_LIBRARY"), reason="requires native BDR library")
def test_real_http_varied_gate_preserves_semantic_failures_and_full_cold_parity():
    report = gate(Path(os.environ["MEMORIA_NATIVE_LIBRARY"]))
    assert report["integrity_status"] == "PASS"
    assert report["integrity_passed"] == report["integrity_total"]
    assert report["checks"]["cold_restart_full_parity"]
    assert report["totals"]["cases"] == 37
    assert report["totals"]["false_positive"] > 0
    assert report["retrieval_quality_status"] == "FAIL_EXTRA_OR_MISSING_CONTENT"
    assert report["factual_quality_status"] == "NOT_EVALUATED"
    assert any(c["category"] == "absent_attribute" and c["false_positive"] for c in report["cases"])
    assert not report["threshold_shadow"]["exact_all_cases_possible"]
