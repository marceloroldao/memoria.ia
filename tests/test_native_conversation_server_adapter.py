from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from memoria_resolutiva.conversation_contract import attach_conversation_routes as attach_server_conversation_routes
from memoria_resolutiva.native_conversation import NativeConversationService
from memoria_resolutiva.product_conversation import ConversationSemanticService, attach_conversation_routes
from memoria_resolutiva.product_evidence import ProductEvidenceService


HEADERS = {"X-Memoria-Key": "secret"}


def _native_library() -> Path:
    value = os.environ.get("MEMORIA_NATIVE_LIB")
    if not value:
        pytest.skip("MEMORIA_NATIVE_LIB is not set; server/native parity runs in the host ABI workflow")
    path = Path(value)
    assert path.is_file()
    return path


def _app(service) -> TestClient:
    app = FastAPI()
    attach_conversation_routes(app, api_key="secret", service=service)
    return TestClient(app)


def _python_service(root: Path) -> ConversationSemanticService:
    evidence = ProductEvidenceService.open(root / "python-evidence", backend="sqlite", allow_fallback=False)
    return ConversationSemanticService(evidence)


def _native_service(root: Path, library: Path) -> NativeConversationService:
    return NativeConversationService(
        library_path=library,
        data_dir=root / "native-state",
        organization_id="conversation-parity-org",
    )


def _ingest(client: TestClient, **payload) -> dict:
    response = client.post("/api/v1/conversation/ingest", json=payload, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def _resolve(client: TestClient, query: str, session_id: str | None) -> dict:
    payload: dict[str, object] = {"query": query}
    if session_id is not None:
        payload["session_id"] = session_id
    response = client.post("/api/v1/conversation/resolve", json=payload, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def _relation_semantics(row: dict) -> tuple:
    return (
        row.get("subject"), row.get("predicate"), row.get("object"),
        row.get("memory_id"), round(float(row.get("confidence", 0.0)), 6), row.get("namespace"),
    )


def _semantic_contract(result: dict) -> dict:
    return {
        "status": result["status"],
        "memory_ids": result["memory_ids"],
        "selected_context": result["selected_context"],
        "relations": [_relation_semantics(row) for row in result["relations"]],
        "roots": [row.get("ultimate_source_memory_id") for row in result["provenance"]],
        "authorities": [round(float(row.get("source_authority", 0.0)), 6) for row in result["provenance"]],
    }


def test_native_conversation_matches_python_core_contract_and_restart(tmp_path: Path):
    library = _native_library()
    python_service = _python_service(tmp_path)
    native_service = _native_service(tmp_path, library)
    try:
        python_client = _app(python_service)
        native_client = _app(native_service)

        p1 = _ingest(python_client, role="user", text="sensor = active", session_id="s1", order=1)
        n1 = _ingest(native_client, role="user", text="sensor = active", session_id="s1", order=1)
        assert n1["stored_memory_ids"] == p1["stored_memory_ids"]
        assert [_relation_semantics(row) for row in n1["relations"]] == [_relation_semantics(row) for row in p1["relations"]]
        assert len(n1["stored_memory_ids"]) == 2

        p2 = _ingest(python_client, role="user", text="sensor = broken", session_id="s2", order=1)
        n2 = _ingest(native_client, role="user", text="sensor = broken", session_id="s2", order=1)
        assert n2["stored_memory_ids"] == p2["stored_memory_ids"]

        python_s1 = _resolve(python_client, "sensor active", "s1")
        native_s1 = _resolve(native_client, "sensor active", "s1")
        assert _semantic_contract(native_s1) == _semantic_contract(python_s1)
        assert "broken" not in native_s1["selected_context"]

        python_s2 = _resolve(python_client, "sensor broken", "s2")
        native_s2 = _resolve(native_client, "sensor broken", "s2")
        assert _semantic_contract(native_s2) == _semantic_contract(python_s2)

        old_p = _ingest(python_client, role="user", text="project = standby", session_id="fix", order=1)
        old_n = _ingest(native_client, role="user", text="project = standby", session_id="fix", order=1)
        assert old_n["stored_memory_ids"] == old_p["stored_memory_ids"]
        corrected_p = _ingest(
            python_client, role="user", text="project = active", session_id="fix", order=2,
            corrects_memory_ids=[old_p["stored_memory_ids"][0]],
        )
        corrected_n = _ingest(
            native_client, role="user", text="project = active", session_id="fix", order=2,
            corrects_memory_ids=[old_n["stored_memory_ids"][0]],
        )
        assert corrected_n["stored_memory_ids"] == corrected_p["stored_memory_ids"]
        assert _semantic_contract(_resolve(native_client, "project active", "fix")) == _semantic_contract(
            _resolve(python_client, "project active", "fix")
        )

        root_p = _ingest(python_client, role="user", text="atlas = 4729", session_id="lineage", order=1)
        root_n = _ingest(native_client, role="user", text="atlas = 4729", session_id="lineage", order=1)
        _ingest(
            python_client, role="assistant", text="atlas = 4729", session_id="lineage", order=2,
            parent_memory_ids=[root_p["stored_memory_ids"][0]],
        )
        _ingest(
            native_client, role="assistant", text="atlas = 4729", session_id="lineage", order=2,
            parent_memory_ids=[root_n["stored_memory_ids"][0]],
        )
        native_lineage = _resolve(native_client, "atlas 4729", "lineage")
        python_lineage = _resolve(python_client, "atlas 4729", "lineage")
        assert native_lineage["status"] == python_lineage["status"] == "HIT"
        assert native_lineage["provenance"][0]["ultimate_source_memory_id"] == root_n["stored_memory_ids"][0]
        assert round(float(native_lineage["provenance"][0]["source_authority"]), 6) == 0.95

        assert _resolve(native_client, "unknown never stored", "s1")["status"] == "UNRESOLVED"
        native_service.flush()
    finally:
        native_service.close()

    reopened = _native_service(tmp_path, library)
    try:
        reopened_client = _app(reopened)
        assert _semantic_contract(_resolve(reopened_client, "sensor active", "s1")) == _semantic_contract(python_s1)
        assert _resolve(reopened_client, "project active", "fix")["status"] == "HIT"
        assert _resolve(reopened_client, "sensor broken", "s2")["selected_context"] == "sensor = broken"
    finally:
        reopened.close()


def test_native_conversation_exposes_temporal_previous_current(tmp_path: Path):
    service = _native_service(tmp_path, _native_library())
    try:
        client = _app(service)
        _ingest(client, role="user", text="device = standby", session_id="temporal", order=1)
        _ingest(client, role="user", text="device = active", session_id="temporal", order=2)
        result = _resolve(client, "what was device before and what is current now?", "temporal")
        assert result["status"] == "HIT"
        assert result["selected_context"] == "PREVIOUS: device = standby\nCURRENT: device = active"
        assert len(result["memory_ids"]) == 2
    finally:
        service.close()


def test_native_conversation_reports_multiple_changes_with_their_own_sources_after_restart(tmp_path):
    library = _native_library()
    service = _native_service(tmp_path, library)
    try:
        client = _app(service)

        def record(text, order, session_id="workshop"):
            return _ingest(client, role="user", text=text, order=order, session_id=session_id)["stored_memory_ids"][0]

        first_12v = record("A fonte Vega fornece 12 volts.", 40)
        old_color = record("A fonte Vega é cinza.", 10)
        old_voltage = record("A fonte Vega fornece 24 volts.", 20)
        current_color = record("A fonte Vega é preta.", 45)
        current_voltage = record("A fonte Vega fornece 12 volts.", 50)
        record("A fonte Vega fica na bancada.", 30)
        record("A fonte Vega fica na bancada.", 60)
        record("A fonte Vega fornece 48 volts.", 80, session_id="other")
        record("A fonte Vega pesa 2 quilos.", 10)
        record("A fonte Vega pesa 3 quilos.", 40)
        record("A fonte Vega pesa 4 quilos.", 40)
        service.flush()
    finally:
        service.close()

    service = _native_service(tmp_path, library)
    try:
        app = FastAPI()
        attach_server_conversation_routes(app, api_key="secret", service=service)
        result = _resolve(TestClient(app), "O que mudou na fonte Vega?", "workshop")
        assert result["status"] == "HIT"
        assert result["memory_ids"] == [old_color, current_color, old_voltage, current_voltage]
        assert [item["memory_id"] for item in result["provenance"]] == result["memory_ids"]
        assert [
            (item["property"], item["previous_value"], item["current_value"],
             item["previous_memory_id"], item["current_memory_id"])
            for item in result["temporal_changes"]
        ] == [
            ("color", "cinza", "preta", old_color, current_color),
            ("voltage", "24 volts", "12 volts", old_voltage, current_voltage),
        ]
        assert [item["predicate"] for item in result["relations"]] == ["color", "voltage"]
        assert result["selected_context"].count("TRANSITION:") == 2
        assert [item["transition_order"] for item in result["temporal_changes"]] == [45, 40]

        client = TestClient(app)
        latest_query = "Qual foi a última mudança na fonte Vega?"
        latest = _resolve(client, latest_query, "workshop")
        assert latest["status"] == "HIT"
        assert latest["memory_ids"] == [old_color, current_color]
        assert [(item["property"], item["transition_order"]) for item in latest["temporal_changes"]] == [
            ("color", 45),
        ]
        _ingest(client, role="user", text="A fonte Vega é preta.", order=70, session_id="workshop")
        _ingest(client, role="user", text="A fonte Vega fica no almoxarifado.", order=65, session_id="workshop")
        newest = _resolve(client, latest_query, "workshop")
        assert [(item["property"], item["transition_order"]) for item in newest["temporal_changes"]] == [
            ("location", 65),
        ]
        _ingest(client, role="user", text="A fonte Vega fornece 18 volts.", order=65, session_id="workshop")
        tied = _resolve(client, latest_query, "workshop")
        assert [(item["property"], item["transition_order"]) for item in tied["temporal_changes"]] == [
            ("voltage", 65), ("location", 65),
        ]
        assert _resolve(client, "Qual foi a última mudança?", "workshop")["status"] == "UNRESOLVED"

        compared = _resolve(client, "O que mudou na fonte Vega entre as ordens 25 e 45?", "workshop")
        assert compared["status"] == "HIT"
        assert compared["memory_ids"] == [old_color, current_color, old_voltage, first_12v]
        assert [item["memory_id"] for item in compared["provenance"]] == compared["memory_ids"]
        assert [
            (item["property"], item["previous_value"], item["current_value"],
             item["from_order"], item["to_order"])
            for item in compared["temporal_changes"]
        ] == [
            ("color", "cinza", "preta", 25, 45),
            ("voltage", "24 volts", "12 volts", 25, 45),
        ]
        assert "ORDEM 25:" in compared["selected_context"]
        assert "ORDEM 45:" in compared["selected_context"]
        assert all("transition_order" not in item for item in compared["temporal_changes"])

        _ingest(client, role="user", text="A fonte Vega fica na bancada.", order=75, session_id="workshop")
        reverted = _resolve(client, "O que mudou na fonte Vega entre as ordens 60 e 75?", "workshop")
        assert [item["property"] for item in reverted["temporal_changes"]] == ["voltage"]
        _ingest(client, role="user", text="A fonte Vega pesa 3 quilos.", order=63, session_id="workshop")
        _ingest(client, role="user", text="A fonte Vega pesa 4 quilos.", order=68, session_id="workshop")
        timeline = _resolve(
            client, "Quais mudanças ocorreram na fonte Vega entre as ordens 60 e 75?", "workshop",
        )
        assert timeline["status"] == "HIT"
        assert [
            (item["property"], item["previous_value"], item["current_value"],
             item["previous_order"], item["transition_order"])
            for item in timeline["temporal_changes"]
        ] == [
            ("voltage", "12 volts", "18 volts", 50, 65),
            ("location", "na bancada", "no almoxarifado", 60, 65),
            ("weight", "3 quilos", "4 quilos", 63, 68),
            ("location", "no almoxarifado", "na bancada", 65, 75),
        ]
        assert [item["memory_id"] for item in timeline["provenance"]] == timeline["memory_ids"]
        assert all(
            (item["from_order"], item["to_order"]) == (60, 75)
            for item in timeline["temporal_changes"]
        )
        assert _resolve(
            client, "Quais mudanças ocorreram na fonte Vega entre as ordens 60 e 64?", "workshop",
        )["status"] == "UNRESOLVED"
        assert _resolve(
            client, "Quais mudanças ocorreram na fonte Vega entre as ordens 75 e 60?", "workshop",
        )["status"] == "UNRESOLVED"

        for question in (
            "O que mudou na fonte Vega entre as ordens 25 e 27?",
            "O que mudou na fonte Vega entre as ordens 5 e 45?",
            "O que mudou na fonte Vega entre as ordens 45 e 25?",
            "O que mudou na fonte Vega entre as ordens -25 e 45?",
            "O que mudou na fonte Vega entre as ordens 25 e 45 ou 60?",
        ):
            assert _resolve(client, question, "workshop")["status"] == "UNRESOLVED"

        for order, expected_id, expected_value in (
            (25, old_color, "cinza"), (45, current_color, "preta"),
        ):
            snapshot = _resolve(client, f"Qual era a cor da fonte Vega na ordem {order}?", "workshop")
            assert snapshot["status"] == "HIT"
            assert snapshot["as_of_order"] == order
            assert snapshot["memory_ids"] == [expected_id]
            assert snapshot["relations"][0]["object"] == expected_value
            assert snapshot["provenance"][0]["created_order"] <= order
        for question in (
            "Qual a cor da fonte Vega na ordem 5?",
            "Qual a cor da fonte Vega na ordem -25?",
            "Qual a cor da fonte Vega na ordem 25 ou 45?",
            "Qual era o peso da fonte Vega na ordem 40?",
            "Qual era a cor da fonte Vega Mini na ordem 25?",
        ):
            assert _resolve(client, question, "workshop")["status"] == "UNRESOLVED"
    finally:
        service.close()
