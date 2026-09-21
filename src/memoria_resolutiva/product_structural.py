from __future__ import annotations

from dataclasses import dataclass
import hmac
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .structural_observation import StructuralObservationStore


class StructuralEventPayload(BaseModel):
    version: int = Field(default=1, ge=1)
    source_id: str = Field(min_length=1, max_length=512)
    sequence: int = Field(ge=0)
    byte_offset: int = Field(ge=0)
    byte_length: int = Field(gt=0)
    trail: list[int] = Field(default_factory=list, max_length=65536)
    relation_ids: list[int] = Field(default_factory=list, max_length=65536)
    signature: str = Field(min_length=16, max_length=16, pattern="^[0-9A-Fa-f]{16}$")
    resolution: int = Field(ge=1, le=32)


class StructuralObservationRequest(BaseModel):
    event: StructuralEventPayload
    provenance: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


@dataclass(slots=True)
class ProductStructuralObservationService:
    store: StructuralObservationStore

    @classmethod
    def open(
        cls,
        root,
        *,
        backend: str | None = None,
        allow_fallback: bool = True,
    ) -> "ProductStructuralObservationService":
        return cls(StructuralObservationStore(root, backend=backend, allow_fallback=allow_fallback))

    def ingest(self, request: StructuralObservationRequest) -> tuple[dict[str, Any], bool]:
        return self.store.append(
            request.event.model_dump(),
            provenance=request.provenance,
        )


def attach_structural_observation_routes(
    app: FastAPI,
    *,
    api_key: str,
    service: ProductStructuralObservationService,
) -> None:
    def require_admin(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    @app.get("/api/v1/structural/health", dependencies=[Depends(require_admin)])
    def structural_health():
        return {
            "status": "ok",
            "format": "memoria.ia-structural-observation-v1",
            "backend": service.store.backend,
            "observations": service.store.count,
            "semantic_projection": False,
        }

    @app.post("/api/v1/structural/observations", status_code=201, dependencies=[Depends(require_admin)])
    def ingest_structural_observation(request: StructuralObservationRequest):
        try:
            envelope, duplicate = service.ingest(request)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "stored": not duplicate,
            "duplicate": duplicate,
            "observation_id": envelope["observation_id"],
            "semantic_projection": False,
            "backend": service.store.backend,
        }

    @app.get("/api/v1/structural/observations/recent", dependencies=[Depends(require_admin)])
    def recent_structural_observations(limit: int = Query(default=20, ge=1, le=100)):
        return {
            "observations": service.store.count,
            "semantic_projection": False,
            "items": list(service.store.recent(limit)),
        }
