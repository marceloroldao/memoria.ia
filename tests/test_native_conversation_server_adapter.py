from __future__ import annotations

import os
from pathlib import Path
from random import Random

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
        weight_a = record("A fonte Vega pesa 3 quilos.", 40)
        weight_b = record("A fonte Vega pesa 4 quilos.", 40)
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
        assert compared["memory_ids"][:4] == [old_color, current_color, old_voltage, first_12v]
        assert set(compared["memory_ids"][4:]) == {weight_a, weight_b}
        assert [item["memory_id"] for item in compared["provenance"]] == compared["memory_ids"]
        blocked = compared["temporal_conflicts"][0]
        assert (blocked["property"], blocked["order"], blocked["endpoint_orders"]) == ("weight", 40, [45])
        assert "Conflito no ponto 45 da comparação" in compared["selected_context"]
        assert {item["memory_id"]: item["value"] for item in blocked["observations"]} == {
            weight_a: "3 quilos", weight_b: "4 quilos",
        }
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

        equal = _resolve(client, "O que mudou na fonte Vega entre as ordens 45 e 55?", "workshop")
        assert equal["status"] == "HIT"
        assert "temporal_changes" not in equal
        assert equal["relations"] == []
        assert equal["memory_ids"][:2] == [first_12v, current_voltage]
        assert set(equal["memory_ids"][2:]) == {weight_a, weight_b}
        assert len(equal["temporal_conflicts"]) == 1
        assert equal["temporal_conflicts"][0]["endpoint_orders"] == [45, 55]
        assert [item["memory_id"] for item in equal["provenance"]] == equal["memory_ids"]
        assert equal["temporal_equal_endpoints"] == [{
            "property": "voltage",
            "previous_value": "12 volts",
            "current_value": "12 volts",
            "previous_memory_id": first_12v,
            "current_memory_id": current_voltage,
            "previous_order": 40,
            "current_order": 50,
            "from_order": 45,
            "to_order": 55,
        }]
        assert "MESMO VALOR NOS DOIS PONTOS" in equal["selected_context"]

        _ingest(client, role="user", text="A fonte Vega fica na bancada.", order=75, session_id="workshop")
        reverted = _resolve(client, "O que mudou na fonte Vega entre as ordens 60 e 75?", "workshop")
        assert [item["property"] for item in reverted["temporal_changes"]] == ["voltage"]
        assert [(item["property"], item["current_value"]) for item in reverted["temporal_equal_endpoints"]] == [
            ("color", "preta"), ("location", "na bancada"),
        ]
        assert [item["predicate"] for item in reverted["relations"]] == ["voltage"]

        recovery = _ingest(
            client, role="user", text="A fonte Vega pesa 3 quilos.", order=63, session_id="workshop",
        )["stored_memory_ids"][0]
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
        inherited = _resolve(
            client, "Quais mudanças ocorreram na fonte Vega entre as ordens 60 e 64?", "workshop",
        )
        assert inherited["status"] == "HIT"
        assert "temporal_changes" not in inherited
        carried = inherited["temporal_conflicts"][0]
        assert (carried["order"], carried["inherited"]) == (40, True)
        assert carried["resume"] == {"memory_id": recovery, "value": "3 quilos", "order": 63}
        assert {item["memory_id"] for item in inherited["provenance"]} == {weight_a, weight_b, recovery}

        still_open = _resolve(
            client, "Quais mudanças ocorreram na fonte Vega entre as ordens 60 e 62?", "workshop",
        )
        assert still_open["temporal_conflicts"][0]["inherited"] is True
        assert still_open["temporal_conflicts"][0]["resume"] is None
        assert _resolve(
            client, "Quais mudanças ocorreram na fonte Vega entre as ordens 63 e 64?", "workshop",
        )["status"] == "UNRESOLVED"
        assert _resolve(
            client, "Quais mudanças ocorreram na fonte Vega entre as ordens 75 e 60?", "workshop",
        )["status"] == "UNRESOLVED"

        mixed = _resolve(
            client, "Quais mudanças ocorreram na fonte Vega entre as ordens 25 e 45?", "workshop",
        )
        assert [item["property"] for item in mixed["temporal_changes"]] == ["voltage", "color"]
        assert len(mixed["temporal_conflicts"]) == 1
        conflict = mixed["temporal_conflicts"][0]
        assert (conflict["property"], conflict["order"]) == ("weight", 40)
        assert {item["memory_id"]: item["value"] for item in conflict["observations"]} == {
            weight_a: "3 quilos", weight_b: "4 quilos",
        }
        assert {weight_a, weight_b} <= {item["memory_id"] for item in mixed["provenance"]}
        assert "CONFLITO na ordem 40" in mixed["selected_context"]

        conflict_only = _resolve(
            client, "Quais mudanças ocorreram na fonte Vega entre as ordens 40 e 41?", "workshop",
        )
        assert conflict_only["status"] == "HIT"
        assert "temporal_changes" not in conflict_only
        assert conflict_only["relations"] == []
        assert set(conflict_only["memory_ids"]) == {weight_a, weight_b}
        assert conflict_only["temporal_conflicts"][0]["observations"] == conflict["observations"]
        assert conflict_only["temporal_conflicts"][0]["inherited"] is False
        assert conflict_only["temporal_conflicts"][0]["resume"] is None

        conflict_comparison = _resolve(
            client, "O que mudou na fonte Vega entre as ordens 41 e 42?", "workshop",
        )
        assert conflict_comparison["status"] == "UNRESOLVED"
        assert "as_of_order" not in conflict_comparison
        assert "temporal_changes" not in conflict_comparison
        assert conflict_comparison["temporal_conflicts"][0]["endpoint_orders"] == [41, 42]
        assert set(conflict_comparison["memory_ids"]) == {weight_a, weight_b}

        recovered_comparison = _resolve(
            client, "O que mudou na fonte Vega entre as ordens 62 e 64?", "workshop",
        )
        assert recovered_comparison["status"] == "UNRESOLVED"
        assert recovered_comparison["temporal_conflicts"][0]["endpoint_orders"] == [62]

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
        for order in (40, 62):
            indeterminate = _resolve(client, f"Qual era o peso da fonte Vega na ordem {order}?", "workshop")
            assert indeterminate["status"] == "UNRESOLVED"
            assert indeterminate["confidence"] == 0.0
            assert indeterminate["as_of_order"] == order
            assert indeterminate["relations"] == []
            assert {item["memory_id"] for item in indeterminate["provenance"]} == {weight_a, weight_b}
            conflict = indeterminate["temporal_conflicts"][0]
            assert (conflict["property"], conflict["order"], conflict["inherited"]) == ("weight", 40, order > 40)
            assert {item["memory_id"]: item["value"] for item in conflict["observations"]} == {
                weight_a: "3 quilos", weight_b: "4 quilos",
            }
        recovered = _resolve(client, "Qual era o peso da fonte Vega na ordem 63?", "workshop")
        assert recovered["status"] == "HIT"
        assert recovered["memory_ids"] == [recovery]
        assert recovered["relations"][0]["object"] == "3 quilos"
        assert "temporal_conflicts" not in recovered

        for question in (
            "Qual a cor da fonte Vega na ordem 5?",
            "Qual a cor da fonte Vega na ordem -25?",
            "Qual a cor da fonte Vega na ordem 25 ou 45?",
            "Qual era a cor da fonte Vega Mini na ordem 25?",
        ):
            assert _resolve(client, question, "workshop")["status"] == "UNRESOLVED"
    finally:
        service.close()


def _latest_event(events, cutoff):
    order = max((order for order in events if order <= cutoff), default=None)
    return (order, events[order]) if order is not None else (None, {})


def _transition_evidence(property_name, before, after):
    before_order, old = before
    after_order, new = after
    (old_value, old_id), = old.items()
    (new_value, new_id), = new.items()
    return property_name, old_value, new_value, before_order, after_order, old_id, new_id


def _response_transition(item):
    return (
        item["property"], item["previous_value"], item["current_value"],
        item["previous_order"], item["current_order"],
        item["previous_memory_id"], item["current_memory_id"],
    )


def _conflict_observations(item):
    return {observation["value"]: observation["memory_id"] for observation in item["observations"]}


def _assert_temporal_sources(result):
    source_ids = set()
    for field in ("temporal_changes", "temporal_equal_endpoints"):
        for item in result.get(field, []):
            source_ids.update((item["previous_memory_id"], item["current_memory_id"]))
    for conflict in result.get("temporal_conflicts", []):
        source_ids.update(_conflict_observations(conflict).values())
        if conflict.get("resume"):
            source_ids.add(conflict["resume"]["memory_id"])
    assert set(result["memory_ids"]) == source_ids
    assert {item["memory_id"] for item in result["provenance"]} == source_ids


@pytest.mark.parametrize("seed", range(6))
def test_generated_temporal_histories_against_reference_after_reopen(tmp_path, seed):
    rng = Random(seed)
    formats = {
        "color": ("cor", "A fonte Semente é {}.", ("cinza", "preta", "verde")),
        "voltage": ("tensão", "A fonte Semente fornece {}.", ("12 volts", "18 volts", "24 volts")),
        "weight": ("peso", "A fonte Semente pesa {}.", ("2 quilos", "3 quilos", "4 quilos")),
    }
    readings = [
        (order, prop, value)
        for order in range(1, 13)
        for prop, (_, _, values) in formats.items()
        for value in rng.sample(values, rng.choices((0, 1, 2, 3), weights=(4, 9, 4, 1))[0])
    ]
    rng.shuffle(readings)
    events = {prop: {} for prop in formats}
    library = _native_library()
    service = _native_service(tmp_path, library)
    try:
        for order, prop, value in readings:
            recorded = service.ingest(
                role="user", text=formats[prop][1].format(value), order=order, session_id="generated",
            )
            events[prop].setdefault(order, {})[value] = recorded.memory_ids[0]
        # These would win at the same order if either namespace or source isolation failed.
        service.ingest(
            role="user", text="A fonte Semente fornece 99 volts.", order=12, session_id="other",
        )
        service.ingest(
            role="assistant", text="A fonte Semente é vermelha.", order=12, session_id="generated",
        )
        service.flush()
    finally:
        service.close()

    service = _native_service(tmp_path, library)
    try:
        app = FastAPI()
        attach_server_conversation_routes(app, api_key="secret", service=service)
        with TestClient(app) as client:
            for prop, (label, _, _) in formats.items():
                for order in range(13):
                    observed_order, observed = _latest_event(events[prop], order)
                    query = f"Qual era {label} da fonte Semente na ordem {order}?"
                    actual = _resolve(client, query, "generated")
                    if len(observed) == 1:
                        assert actual["status"] == "HIT", query
                        assert actual["as_of_order"] == order
                        assert actual["relations"][0]["object"] == next(iter(observed))
                    else:
                        assert actual["status"] == "UNRESOLVED", query
                        assert actual["relations"] == []
                    assert set(actual["memory_ids"]) == set(observed.values()), query
                    assert {row["memory_id"] for row in actual["provenance"]} == set(observed.values())
                    if len(observed) > 1:
                        (conflict,) = actual["temporal_conflicts"]
                        assert conflict["order"] == observed_order
                        assert _conflict_observations(conflict) == observed
                    else:
                        assert "temporal_conflicts" not in actual

            windows = [(left, left + 1) for left in range(12)] + [(0, 3), (0, 12), (2, 9), (4, 12)]
            for left, right in windows:
                expected_changes, expected_equal, blocked = [], [], {}
                expected_trace, interruptions = [], {}
                for prop, history in events.items():
                    start = _latest_event(history, left)
                    end = _latest_event(history, right)
                    for cutoff, (event_order, values) in ((left, start), (right, end)):
                        if len(values) > 1:
                            blocked.setdefault((prop, event_order), []).append(cutoff)
                    if len(start[1]) == len(end[1]) == 1 and start[0] != end[0]:
                        transition = _transition_evidence(prop, start, end)
                        (expected_equal if transition[1] == transition[2] else expected_changes).append(transition)

                    trace = [start] if start[0] is not None else []
                    trace.extend(sorted((order, values) for order, values in history.items() if left < order <= right))
                    for before, after in zip(trace, trace[1:]):
                        if len(before[1]) == len(after[1]) == 1 and before[1].keys() != after[1].keys():
                            expected_trace.append(_transition_evidence(prop, before, after))
                    for order, values in trace:
                        if len(values) <= 1:
                            continue
                        next_reading = next(((n, v) for n, v in trace if n > order and len(v) == 1), None)
                        if next_reading:
                            next_order, next_values = next_reading
                            (next_value, next_id), = next_values.items()
                            resume = {"order": next_order, "value": next_value, "memory_id": next_id}
                        else:
                            resume = None
                        interruptions[prop, order] = (values, order < left, resume)

                suffix = f"na fonte Semente entre as ordens {left} e {right}?"
                comparison = _resolve(client, f"O que mudou {suffix}", "generated")
                assert comparison["status"] == ("HIT" if expected_changes or expected_equal else "UNRESOLVED"), suffix
                assert [_response_transition(item) for item in comparison.get("temporal_changes", [])] == expected_changes
                assert [_response_transition(item) for item in comparison.get("temporal_equal_endpoints", [])] == expected_equal
                comparison_conflicts = comparison.get("temporal_conflicts", [])
                assert {(item["property"], item["order"]): item["endpoint_orders"] for item in comparison_conflicts} == blocked
                for item in comparison_conflicts:
                    assert _conflict_observations(item) == events[item["property"]][item["order"]]

                _assert_temporal_sources(comparison)

                timeline = _resolve(client, f"Quais mudanças ocorreram {suffix}", "generated")
                assert timeline["status"] == ("HIT" if expected_trace or interruptions else "UNRESOLVED"), suffix
                timeline_changes = timeline.get("temporal_changes", [])
                assert [_response_transition(item) for item in timeline_changes] == sorted(
                    expected_trace, key=lambda change: (change[4], tuple(formats).index(change[0])),
                )
                assert [item["transition_order"] for item in timeline_changes] == [item["current_order"] for item in timeline_changes]
                assert {
                    (item["property"], item["order"]): (_conflict_observations(item), item["inherited"], item["resume"])
                    for item in timeline.get("temporal_conflicts", [])
                } == interruptions
                _assert_temporal_sources(timeline)
    finally:
        service.close()
