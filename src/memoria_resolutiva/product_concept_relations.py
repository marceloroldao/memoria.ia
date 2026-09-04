from __future__ import annotations

from dataclasses import dataclass
import hmac

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .concept_relations import ConceptRelationView


class ConceptRelationInferRequest(BaseModel):
    source: str = Field(min_length=1, max_length=512)
    target: str = Field(min_length=1, max_length=512)
    namespace: str | None = Field(default=None, max_length=256)
    context: str | None = Field(default=None, max_length=4000)
    max_hops: int = Field(default=3, ge=1, le=32)
    max_paths: int = Field(default=5, ge=1, le=100)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


@dataclass(slots=True)
class ProductConceptRelationService:
    """Structured product boundary for read-only concept relation traversal."""

    view: ConceptRelationView

    def infer(self, request: ConceptRelationInferRequest):
        return self.view.infer_path(
            request.source,
            request.target,
            namespace=request.namespace,
            context=request.context,
            max_hops=request.max_hops,
            max_paths=request.max_paths,
            min_confidence=request.min_confidence,
        )


def _endpoint_payload(endpoint) -> dict:
    return {
        "surface": endpoint.surface,
        "key": endpoint.key,
        "concept_id": endpoint.concept_id,
        "sense_key": endpoint.sense_key,
        "status": endpoint.status,
    }


def attach_concept_relation_routes(
    app: FastAPI,
    *,
    api_key: str,
    service: ProductConceptRelationService,
) -> None:
    def require_admin(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    @app.get("/api/v1/semantic/relations/health", dependencies=[Depends(require_admin)])
    def concept_relation_health():
        return {
            "status": "ok",
            "capability": "concept-relation-traversal-v1",
            "read_only": True,
            "concept_namespace": service.view.concept_namespace,
        }

    @app.post("/api/v1/semantic/relations/infer", dependencies=[Depends(require_admin)])
    def concept_relation_infer(request: ConceptRelationInferRequest):
        try:
            result = service.infer(request)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "status": result.status,
            "source": request.source,
            "target": request.target,
            "namespace": request.namespace,
            "reason": result.reason,
            "paths": [
                {
                    "nodes": [_endpoint_payload(endpoint) for endpoint in path.nodes],
                    "predicates": list(path.predicates),
                    "evidence_ids": list(path.evidence_ids),
                    "source_texts": list(path.source_texts),
                    "confidence": path.confidence,
                    "hops": path.hops,
                }
                for path in result.paths
            ],
        }
