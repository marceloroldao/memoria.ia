from __future__ import annotations

from dataclasses import dataclass
import hmac
import json
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .evidence_core import EvidenceCore
from .evidence_state import EvidenceCorePersistence, EvidenceStateReceipt


class EvidenceRelationRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=512)
    predicate: str = Field(min_length=1, max_length=128)
    object: str = Field(min_length=1, max_length=512)
    evidence_id: str = Field(min_length=1, max_length=256)
    source_text: str = Field(min_length=1, max_length=20000)
    provenance: str = Field(default="api", min_length=1, max_length=256)
    origin: str | None = Field(default=None, max_length=256)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    namespace: str | None = Field(default=None, max_length=256)
    epoch: int | None = Field(default=None, ge=0)


class EvidenceInferRequest(BaseModel):
    source: str = Field(min_length=1, max_length=512)
    target: str = Field(min_length=1, max_length=512)
    namespace: str | None = Field(default=None, max_length=256)
    epoch: int | None = Field(default=None, ge=0)
    max_hops: int = Field(default=3, ge=1, le=32)
    max_paths: int = Field(default=5, ge=1, le=100)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    min_independent_origins: int = Field(default=1, ge=1)
    min_origin_reliability: float | None = Field(default=None, ge=0.0, le=1.0)
    reliability_metric: str = Field(default="posterior", pattern="^(posterior|wilson)$")


@dataclass(slots=True)
class ProductEvidenceService:
    core: EvidenceCore
    persistence: EvidenceCorePersistence
    receipt_path: Path
    receipt: EvidenceStateReceipt | None = None

    @classmethod
    def open(
        cls,
        root: str | Path,
        *,
        backend: str | None = None,
        allow_fallback: bool = True,
    ) -> "ProductEvidenceService":
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        persistence = EvidenceCorePersistence(
            root / "persistence",
            backend=backend,
            allow_fallback=allow_fallback,
        )
        receipt_path = root / "receipt.json"
        if receipt_path.exists():
            raw = json.loads(receipt_path.read_text("utf-8"))
            receipt = EvidenceStateReceipt(
                backend=str(raw["backend"]),
                state_id=str(raw["state_id"]),
                sha256=str(raw["sha256"]),
            )
            core = persistence.load(receipt)
            return cls(core, persistence, receipt_path, receipt)
        return cls(EvidenceCore(), persistence, receipt_path, None)

    def save(self) -> EvidenceStateReceipt:
        receipt = self.persistence.store(self.core)
        tmp = self.receipt_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(receipt.as_dict(), sort_keys=True), "utf-8")
        tmp.replace(self.receipt_path)
        self.receipt = receipt
        return receipt

    @property
    def backend(self) -> str:
        if self.receipt is not None:
            return self.receipt.backend
        return self.persistence.last_backend or "not-initialized"


def attach_evidence_routes(
    app: FastAPI,
    *,
    api_key: str,
    service: ProductEvidenceService,
) -> None:
    def require_admin(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    @app.get("/api/v1/evidence/health", dependencies=[Depends(require_admin)])
    def evidence_health():
        return {
            "status": "ok",
            "core": "evidence-core-v1",
            "backend": service.backend,
            "persisted": service.receipt is not None,
            "state_id": None if service.receipt is None else service.receipt.state_id,
        }

    @app.post("/api/v1/evidence/relations", status_code=201, dependencies=[Depends(require_admin)])
    def ingest_relation(request: EvidenceRelationRequest):
        try:
            edge = service.core.observe_relation(
                request.subject,
                request.predicate,
                request.object,
                evidence_id=request.evidence_id,
                source_text=request.source_text,
                provenance=request.provenance,
                origin=request.origin,
                confidence=request.confidence,
                namespace=request.namespace,
                epoch=request.epoch,
            )
            receipt = service.save()
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "stored": True,
            "edge": {
                "subject": edge.subject,
                "predicate": edge.predicate,
                "object": edge.object,
                "evidence_id": edge.evidence_id,
                "namespace": edge.namespace,
                "epoch": edge.epoch,
                "provenance": edge.provenance,
                "origin": edge.origin,
                "confidence": edge.confidence,
            },
            "persistence": receipt.as_dict(),
        }

    @app.post("/api/v1/evidence/infer", dependencies=[Depends(require_admin)])
    def infer(request: EvidenceInferRequest):
        try:
            result = service.core.infer_path(
                request.source,
                request.target,
                namespace=request.namespace,
                epoch=request.epoch,
                max_hops=request.max_hops,
                max_paths=request.max_paths,
                min_confidence=request.min_confidence,
                min_independent_origins=request.min_independent_origins,
                min_origin_reliability=request.min_origin_reliability,
                reliability_metric=request.reliability_metric,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "source": result.source,
            "target": result.target,
            "inferred": result.inferred,
            "unsupported_claims": result.unsupported_claims,
            "paths": [
                {
                    "nodes": list(path.nodes),
                    "predicates": list(path.predicates),
                    "evidence_ids": list(path.evidence_ids),
                    "source_texts": list(path.source_texts),
                    "origins_by_edge": [list(items) for items in path.origins_by_edge],
                    "confidences": list(path.confidences),
                    "reliabilities": list(path.reliabilities),
                    "hops": path.hops,
                    "confidence": path.confidence,
                    "independent_origin_floor": path.independent_origin_floor,
                    "reliability_floor": path.reliability_floor,
                    "kind": path.kind,
                    "synthesized_claims": path.synthesized_claims,
                }
                for path in result.paths
            ],
        }
