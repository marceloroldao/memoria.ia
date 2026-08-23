from __future__ import annotations

from pathlib import Path
import hmac

try:
    from fastapi import Depends, FastAPI, Header, HTTPException
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("install memoria-resolutiva[product] for the HTTP product API") from exc

from .product_identity import MemoryScope, NodeIdentity
from .product_service import EnterpriseMemoryService, OrganizationMismatch

API_PREFIX = "/api/v1"


class ScopeModel(BaseModel):
    application_id: str | None = None
    agent_id: str | None = None
    user_id: str | None = None


class StoreMemoryRequest(BaseModel):
    knowledge_id: str = Field(min_length=1, max_length=256)
    key: str = Field(min_length=1, max_length=512)
    payload: object
    modality: str = Field(default="text", min_length=1, max_length=64)
    provenance: str = Field(default="api", min_length=1, max_length=256)
    scope: ScopeModel = ScopeModel()


class ResolveMemoryRequest(BaseModel):
    key: str = Field(min_length=1, max_length=512)
    scope: ScopeModel = ScopeModel()


def create_app(
    service: EnterpriseMemoryService,
    *,
    api_key: str,
    data_dir: str | Path | None = None,
    node_identity: NodeIdentity | None = None,
) -> FastAPI:
    if not api_key:
        raise ValueError("api_key must be configured")
    persist_root = Path(data_dir) if data_dir is not None else None

    app = FastAPI(
        title="Memoria.ia Enterprise",
        version="product-alpha",
        docs_url="/docs",
        redoc_url=None,
    )

    def require_api_key(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    def scope_from(model: ScopeModel) -> MemoryScope:
        return MemoryScope(
            service.organization.organization_id,
            application_id=model.application_id,
            agent_id=model.agent_id,
            user_id=model.user_id,
        )

    @app.get(f"{API_PREFIX}/health")
    def health():
        return {"status": "ok", "product": "memoria.ia-enterprise", "maturity": "product-alpha"}

    @app.get(f"{API_PREFIX}/admin/status", dependencies=[Depends(require_api_key)])
    def admin_status():
        identity = None
        if node_identity is not None:
            identity = {
                "organization_id": node_identity.organization_id,
                "node_id": node_identity.node_id,
                "certificate_status": node_identity.certificate_status.value,
                "license_status": node_identity.license_status.value,
                "capabilities": sorted(node_identity.capabilities),
            }
        return {
            "organization": {
                "organization_id": service.organization.organization_id,
                "display_name": service.organization.display_name,
            },
            "node": identity,
            "memory": service.statistics,
            "semantic_routing": "experimental",
            "security_status": "not-security-reviewed",
        }

    @app.post(f"{API_PREFIX}/memories", status_code=201, dependencies=[Depends(require_api_key)])
    def store_memory(request: StoreMemoryRequest):
        scope = scope_from(request.scope)
        try:
            service.remember(
                scope,
                request.knowledge_id,
                request.payload,
                ("key", request.key),
                modality=request.modality,
                provenance=request.provenance,
            )
            if persist_root is not None:
                service.save(persist_root)
        except (ValueError, OrganizationMismatch) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"stored": True, "knowledge_id": request.knowledge_id, "key": request.key}

    @app.post(f"{API_PREFIX}/memories/resolve", dependencies=[Depends(require_api_key)])
    def resolve_memory(request: ResolveMemoryRequest):
        scope = scope_from(request.scope)
        record = service.recall(scope, ("key", request.key))
        if record is None:
            return {"hit": False, "record": None}
        return {
            "hit": True,
            "record": {
                "organization_id": record.organization_id,
                "knowledge_id": record.knowledge_id,
                "payload": record.payload,
                "modality": record.modality,
                "provenance": list(record.provenance),
                "accesses": record.accesses,
            },
        }

    return app
