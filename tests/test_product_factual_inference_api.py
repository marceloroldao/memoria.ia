from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex
from memoria_resolutiva.product_evidence import ProductEvidenceService, attach_evidence_routes


def test_api_can_explicitly_block_generated_premise_from_factual_inference(tmp_path):
    service = ProductEvidenceService.open(tmp_path / "evidence")
    service.core.observe_relation(
        "Delta", "powers", "controller",
        evidence_id="fact-1", source_text="Delta powers controller",
        provenance="conversation", origin="user", namespace="lab", epoch=0,
    )
    service.core.observe_relation(
        "controller", "belongs_to", "Orion",
        evidence_id="gen-1", source_text="The controller belongs to Orion",
        provenance="conversation", origin="assistant", namespace="lab", epoch=1,
    )
    provenance = MemoryProvenanceIndex(service.core)
    provenance.register("fact-1", source_type="user_assertion", namespace="lab")
    provenance.register("gen-1", source_type="assistant_generated", namespace="lab")

    app = FastAPI()
    attach_evidence_routes(app, api_key="secret", service=service)
    client = TestClient(app)
    headers = {"X-Memoria-Key": "secret"}
    base = {"source": "Delta", "target": "Orion", "namespace": "lab", "max_hops": 2}

    historical = client.post("/api/v1/evidence/infer", headers=headers, json=base)
    assert historical.status_code == 200
    assert historical.json()["inferred"] is True
    assert historical.json()["factual_only"] is False

    factual = client.post(
        "/api/v1/evidence/infer", headers=headers, json={**base, "factual_only": True}
    )
    assert factual.status_code == 200
    assert factual.json()["factual_only"] is True
    assert factual.json()["inferred"] is False
    assert factual.json()["paths"] == []
