from __future__ import annotations

from pathlib import Path
import hmac

try:
    from fastapi import Depends, FastAPI, Header, HTTPException
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("install memoria-resolutiva[product] for the HTTP product API") from exc

from .llm_adapter import LLMAdapterError
from .product_chat import ProductChatService, token_reduction
from .product_identity import MemoryScope, NodeIdentity
from .product_service import EnterpriseMemoryService, MemoryRevoked, OrganizationMismatch

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


class UpdateMemoryRequest(BaseModel):
    payload: object
    modality: str = Field(default="text", min_length=1, max_length=64)
    provenance: str = Field(default="api-update", min_length=1, max_length=256)
    scope: ScopeModel = ScopeModel()


class ResolveMemoryRequest(BaseModel):
    key: str = Field(min_length=1, max_length=512)
    scope: ScopeModel = ScopeModel()
    include_revoked: bool = False
    version: int | None = Field(default=None, ge=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    mode: str = Field(default="memoria", pattern="^(baseline|memoria)$")
    baseline_context: list[str] = Field(default_factory=list)
    memory_keys: list[str] = Field(default_factory=list)
    scope: ScopeModel = ScopeModel()


class CompareChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    baseline_context: list[str] = Field(default_factory=list)
    memory_keys: list[str] = Field(default_factory=list)
    scope: ScopeModel = ScopeModel()


def create_app(
    service: EnterpriseMemoryService,
    *,
    api_key: str,
    data_dir: str | Path | None = None,
    node_identity: NodeIdentity | None = None,
    chat_service: ProductChatService | None = None,
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

    def persist() -> None:
        if persist_root is not None:
            service.save(persist_root)

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
        llm = None
        if chat_service is not None:
            llm = {
                "provider": chat_service.adapter.provider_name,
                "model": chat_service.adapter.model_name,
            }
        return {
            "organization": {
                "organization_id": service.organization.organization_id,
                "display_name": service.organization.display_name,
            },
            "node": identity,
            "memory": service.statistics,
            "llm": llm,
            "semantic_routing": "experimental",
            "security_status": "not-security-reviewed",
        }

    @app.post(f"{API_PREFIX}/memories", status_code=201, dependencies=[Depends(require_api_key)])
    def store_memory(request: StoreMemoryRequest):
        scope = scope_from(request.scope)
        try:
            record = service.remember(
                scope,
                request.knowledge_id,
                request.payload,
                ("key", request.key),
                modality=request.modality,
                provenance=request.provenance,
            )
            persist()
        except (ValueError, OrganizationMismatch) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "stored": True,
            "knowledge_id": request.knowledge_id,
            "key": request.key,
            "version": record.version,
        }

    @app.put(f"{API_PREFIX}/memories/{{key}}", dependencies=[Depends(require_api_key)])
    def update_memory(key: str, request: UpdateMemoryRequest):
        scope = scope_from(request.scope)
        try:
            record = service.update(
                scope,
                ("key", key),
                request.payload,
                modality=request.modality,
                provenance=request.provenance,
            )
            persist()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except MemoryRevoked as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"updated": True, "key": key, "version": record.version}

    @app.delete(f"{API_PREFIX}/memories/{{key}}", dependencies=[Depends(require_api_key)])
    def revoke_memory(key: str, application_id: str | None = None, agent_id: str | None = None, user_id: str | None = None):
        scope = MemoryScope(
            service.organization.organization_id,
            application_id=application_id,
            agent_id=agent_id,
            user_id=user_id,
        )
        try:
            service.revoke(scope, ("key", key))
            persist()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"revoked": True, "key": key}

    @app.post(f"{API_PREFIX}/memories/resolve", dependencies=[Depends(require_api_key)])
    def resolve_memory(request: ResolveMemoryRequest):
        scope = scope_from(request.scope)
        record = service.recall(
            scope,
            ("key", request.key),
            include_revoked=request.include_revoked,
            version=request.version,
        )
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
                "version": record.version,
                "revoked": record.revoked,
            },
        }

    @app.post(f"{API_PREFIX}/chat", dependencies=[Depends(require_api_key)])
    def chat(request: ChatRequest):
        if chat_service is None:
            raise HTTPException(status_code=503, detail="LLM adapter is not configured")
        try:
            result = chat_service.run(
                scope=scope_from(request.scope),
                message=request.message,
                mode=request.mode,
                baseline_context=request.baseline_context,
                memory_keys=request.memory_keys,
            )
        except LLMAdapterError as exc:
            raise HTTPException(status_code=503, detail="LLM provider unavailable") from exc
        return {
            "text": result.text,
            "context": list(result.context),
            "metrics": result.metrics.as_dict(),
        }

    @app.post(f"{API_PREFIX}/chat/compare", dependencies=[Depends(require_api_key)])
    def compare_chat(request: CompareChatRequest):
        if chat_service is None:
            raise HTTPException(status_code=503, detail="LLM adapter is not configured")
        scope = scope_from(request.scope)
        try:
            baseline = chat_service.run(
                scope=scope,
                message=request.message,
                mode="baseline",
                baseline_context=request.baseline_context,
            )
            memoria = chat_service.run(
                scope=scope,
                message=request.message,
                mode="memoria",
                memory_keys=request.memory_keys,
            )
        except LLMAdapterError as exc:
            raise HTTPException(status_code=503, detail="LLM provider unavailable") from exc
        reduction = token_reduction(
            baseline_tokens=baseline.metrics.input_tokens,
            memoria_tokens=memoria.metrics.input_tokens,
        )
        return {
            "baseline": {"text": baseline.text, "metrics": baseline.metrics.as_dict()},
            "memoria": {"text": memoria.text, "metrics": memoria.metrics.as_dict()},
            "token_reduction": reduction,
            "token_reduction_percent": None if reduction is None else reduction * 100.0,
        }

    return app
