from __future__ import annotations

from dataclasses import asdict, dataclass
import hmac
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .structural_association_runtime import StructuralAssociationRuntime
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


class StructuralProvenancePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    hierarchy_id: str = Field(min_length=1, max_length=512)


class StructuralObservationRequest(BaseModel):
    event: StructuralEventPayload
    provenance: StructuralProvenancePayload


@dataclass(slots=True)
class ProductStructuralObservationService:
    store: StructuralObservationStore
    associations: StructuralAssociationRuntime

    @classmethod
    def open(
        cls,
        root,
        *,
        backend: str | None = None,
        allow_fallback: bool = True,
    ) -> "ProductStructuralObservationService":
        root = Path(root)
        store = StructuralObservationStore(
            root,
            backend=backend,
            allow_fallback=allow_fallback,
        )
        associations = StructuralAssociationRuntime(
            store,
            root / "associations",
            backend=backend,
            allow_fallback=allow_fallback,
        )
        return cls(store, associations)

    def ingest(self, request: StructuralObservationRequest) -> tuple[dict[str, Any], bool, int]:
        envelope, duplicate = self.store.append(
            request.event.model_dump(),
            provenance=request.provenance.model_dump(),
        )
        try:
            replayed = self.associations.sync()
        except Exception as exc:
            raise RuntimeError("structural association sync failed") from exc
        return envelope, duplicate, replayed


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
        association_status = service.associations.status()
        return {
            "status": "ok",
            "format": "memoria.ia-structural-observation-v1",
            "backend": service.store.backend,
            "observations": service.store.count,
            "semantic_projection": False,
            "associations": association_status,
        }

    @app.post("/api/v1/structural/observations", status_code=201, dependencies=[Depends(require_admin)])
    def ingest_structural_observation(request: StructuralObservationRequest):
        try:
            envelope, duplicate, replayed = service.ingest(request)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "stored": not duplicate,
            "duplicate": duplicate,
            "observation_id": envelope["observation_id"],
            "association_sync_observations": replayed,
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


    @app.get("/api/v1/structural/associations/status", dependencies=[Depends(require_admin)])
    def structural_association_status():
        return service.associations.status()

    @app.get("/api/v1/structural/associations", dependencies=[Depends(require_admin)])
    def structural_associations(
        hierarchy_id: str = Query(min_length=1, max_length=512),
        source: int = Query(ge=0),
        channel: str | None = Query(default=None, pattern="^(within|temporal)$"),
        limit: int = Query(default=10, ge=1, le=100),
    ):
        rows = service.associations.strongest(
            hierarchy_id,
            source,
            channel=channel,
            top_k=limit,
        )
        return {
            "hierarchy_id": hierarchy_id,
            "source": source,
            "channel": channel,
            "semantic_projection": False,
            "associations": [asdict(row) for row in rows],
        }
