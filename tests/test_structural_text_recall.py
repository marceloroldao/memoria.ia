from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from memoria_resolutiva.product_structural import (
    ProductStructuralObservationService,
    attach_structural_observation_routes,
)
from memoria_resolutiva.structural_association_runtime import StructuralAssociationRuntime
from memoria_resolutiva.structural_observation import StructuralObservationStore
from memoria_resolutiva.structural_text_recall import (
    StructuralTextRecall,
    structural_text_symbol,
)


def _open(tmp_path):
    raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    runtime = StructuralAssociationRuntime(
        raw,
        tmp_path / "derived",
        backend="sqlite",
        allow_fallback=False,
        forgetting_rate=0.0,
    )
    return raw, runtime, StructuralTextRecall(raw, runtime)


def test_structural_text_gate_recovers_context_without_llm_and_query_is_read_only(tmp_path):
    raw, _runtime, recall = _open(tmp_path)
    recall.observe(
        "Meu gato se chama Alt",
        hierarchy_id="offia:session-1",
        source_id="offia:user",
        sequence=0,
    )
    recall.observe(
        "Meu cachorro se chama Rex",
        hierarchy_id="offia:session-1",
        source_id="offia:user",
        sequence=1,
    )

    before = raw.count
    result = recall.resolve(
        "Qual é o nome do meu gato?",
        hierarchy_id="offia:session-1",
        top_k=2,
    )

    assert raw.count == before
    assert result.status == "HIT"
    assert result.semantic_projection is False
    assert result.contexts
    assert result.contexts[0].source_text == "Meu gato se chama Alt"
    assert result.contexts[0].exact_overlap >= 2


def test_repetition_reinforces_structure_without_predicate_rules(tmp_path):
    _raw, runtime, recall = _open(tmp_path)
    recall.observe(
        "Meu gato se chama Alt",
        hierarchy_id="offia:session-2",
        source_id="offia:user",
        sequence=0,
    )
    recall.observe(
        "Meu gato se chama Alt",
        hierarchy_id="offia:session-2",
        source_id="offia:user",
        sequence=1,
    )
    recall.observe(
        "Meu gato dorme no sofa",
        hierarchy_id="offia:session-2",
        source_id="offia:user",
        sequence=2,
    )

    gato = structural_text_symbol("gato")
    se = structural_text_symbol("se")
    dorme = structural_text_symbol("dorme")
    repeated = runtime.association(
        "offia:session-2",
        gato,
        se,
        channel="within",
    )
    single = runtime.association(
        "offia:session-2",
        gato,
        dorme,
        channel="within",
    )

    assert repeated > single
    result = recall.resolve(
        "gato",
        hierarchy_id="offia:session-2",
        top_k=2,
    )
    assert result.status == "HIT"
    assert result.contexts[0].source_text == "Meu gato se chama Alt"


def test_structural_text_restart_preserves_recall(tmp_path):
    raw, _runtime, recall = _open(tmp_path)
    recall.observe(
        "Minha camisa era azul",
        hierarchy_id="offia:session-3",
        source_id="offia:user",
        sequence=0,
    )
    recall.observe(
        "Minha camisa ficou preta",
        hierarchy_id="offia:session-3",
        source_id="offia:user",
        sequence=1,
    )
    before = recall.resolve(
        "camisa preta",
        hierarchy_id="offia:session-3",
        top_k=2,
    )

    reopened_raw = StructuralObservationStore(
        tmp_path / "raw",
        backend="sqlite",
        allow_fallback=False,
    )
    reopened_runtime = StructuralAssociationRuntime(
        reopened_raw,
        tmp_path / "derived",
        backend="sqlite",
        allow_fallback=False,
    )
    reopened = StructuralTextRecall(reopened_raw, reopened_runtime)
    after = reopened.resolve(
        "camisa preta",
        hierarchy_id="offia:session-3",
        top_k=2,
    )

    assert reopened_raw.count == raw.count
    assert reopened_runtime.replayed_on_open == 0
    assert after.status == before.status == "HIT"
    assert [item.source_text for item in after.contexts] == [
        item.source_text for item in before.contexts
    ]
    assert after.contexts[0].source_text == "Minha camisa ficou preta"


def test_structural_text_http_contract_is_authenticated_and_semantic_free(tmp_path):
    service = ProductStructuralObservationService.open(
        tmp_path / "structural",
        backend="sqlite",
        allow_fallback=False,
    )
    app = FastAPI()
    attach_structural_observation_routes(app, api_key="secret", service=service)
    client = TestClient(app)
    headers = {"X-Memoria-Key": "secret"}

    denied = client.post(
        "/api/v1/structural/text/observe",
        json={
            "text": "Meu gato se chama Alt",
            "hierarchy_id": "offia:http",
            "source_id": "offia:user",
            "sequence": 0,
        },
    )
    assert denied.status_code == 401

    observed = client.post(
        "/api/v1/structural/text/observe",
        headers=headers,
        json={
            "text": "Meu gato se chama Alt",
            "hierarchy_id": "offia:http",
            "source_id": "offia:user",
            "sequence": 0,
        },
    )
    assert observed.status_code == 201
    assert observed.json()["stored"] is True
    assert observed.json()["semantic_projection"] is False

    duplicate = client.post(
        "/api/v1/structural/text/observe",
        headers=headers,
        json={
            "text": "Meu gato se chama Alt",
            "hierarchy_id": "offia:http",
            "source_id": "offia:user",
            "sequence": 0,
        },
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["duplicate"] is True

    before = service.store.count
    resolved = client.post(
        "/api/v1/structural/text/resolve",
        headers=headers,
        json={
            "query": "qual nome do meu gato",
            "hierarchy_id": "offia:http",
            "limit": 3,
        },
    )
    assert resolved.status_code == 200
    payload = resolved.json()
    assert payload["status"] == "HIT"
    assert payload["semantic_projection"] is False
    assert payload["contexts"][0]["source_text"] == "Meu gato se chama Alt"
    assert service.store.count == before
