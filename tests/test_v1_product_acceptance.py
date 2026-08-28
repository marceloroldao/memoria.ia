from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from memoria_resolutiva.bdr_store import native_bdr_available


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "v1_product_acceptance.py"
SPEC = importlib.util.spec_from_file_location("v1_product_acceptance", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _assert_report(report: dict, backend: str) -> None:
    assert report["acceptance"] == "memoria.ia-v1-candidate-product-acceptance"
    assert report["backend"] == backend
    assert report["overall"] == "PASS", report
    assert report["counts"]["FAIL"] == 0
    assert report["metrics"]["chat_calls"] > 0
    assert report["metrics"]["memory_hits"] > 0
    assert report["compare"]["token_reduction"] is not None


def test_v1_product_long_session_sqlite_acceptance():
    report = MODULE.run_acceptance(backend="sqlite", turns=24)
    _assert_report(report, "sqlite")


@pytest.mark.skipif(not native_bdr_available(), reason="native BDR extension not built")
def test_v1_product_long_session_native_bdr_acceptance():
    report = MODULE.run_acceptance(backend="bdr", turns=24)
    _assert_report(report, "bdr")
