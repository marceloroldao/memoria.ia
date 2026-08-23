import json

from memoria_resolutiva import product_identity  # proves package import path is available

from experiments.product_alpha_acceptance import run_gate


def test_acceptance_gate_has_15_unique_criteria(tmp_path):
    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text(json.dumps({"benchmark": "memoria.ia-product-context-v1", "summary": {}}), "utf-8")
    report = run_gate(tests_passed=True, container_validated=True, benchmark_file=benchmark)
    assert len(report["criteria"]) == 15
    assert [item["id"] for item in report["criteria"]] == list(range(1, 16))
    assert report["counts"]["FAIL"] == 0


def test_live_llm_criteria_remain_partial_without_external_call(tmp_path):
    report = run_gate(tests_passed=True, container_validated=True, benchmark_file=None)
    by_id = {item["id"]: item for item in report["criteria"]}
    assert by_id[5]["status"] == "PARTIAL"
    assert by_id[6]["status"] == "PARTIAL"
    assert by_id[15]["status"] == "PARTIAL"
    assert report["overall"] == "PARTIAL"
