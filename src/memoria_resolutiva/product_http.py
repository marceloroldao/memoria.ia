from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hmac

try:
    from fastapi import Depends, FastAPI, Header, HTTPException
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("install memoria-resolutiva[product] for the HTTP product API") from exc

from .llm_adapter import LLMAdapterError
from .product_applications import ApplicationAuth, ApplicationRegistry
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


class CreateApplicationRequest(BaseModel):
    application_id: str = Field(min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=256)
    scopes: list[str] = Field(default_factory=lambda: ["memory.read", "memory.write", "chat.use"])


@dataclass(frozen=True, slots=True)
class AuthContext:
    is_admin: bool
    application: ApplicationAuth | None = None



def create_app(
    service: EnterpriseMemoryService,
    *,
    api_key: str,
    data_dir: str | Path | None = None,
    node_identity: NodeIdentity | None = None,
    chat_service: ProductChatService | None = None,
    application_registry: ApplicationRegistry | None = None,
    lifespan=None,
) -> FastAPI:
    if not api_key:
        raise ValueError("api_key must be configured")
    persist_root = Path(data_dir) if data_dir is not None else None

    app = FastAPI(
        title="Memoria.ia Enterprise",
        version="product-alpha",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    web_root = Path(__file__).with_name("webui")
    app.mount("/ui", StaticFiles(directory=web_root), name="ui")

    @app.get("/", include_in_schema=False)
    def web_ui():
        return FileResponse(web_root / "index.html")

    def authenticate(x_memoria_key: str | None = Header(default=None)) -> AuthContext:
        if x_memoria_key is None:
            raise HTTPException(status_code=401, detail="invalid API credentials")
        if hmac.compare_digest(x_memoria_key, api_key):
            return AuthContext(is_admin=True)
        if application_registry is not None:
            application = application_registry.authenticate(x_memoria_key)
            if application is not None:
                return AuthContext(is_admin=False, application=application)
        raise HTTPException(status_code=401, detail="invalid API credentials")

    def require_admin(auth: AuthContext = Depends(authenticate)) -> AuthContext:
        if not auth.is_admin:
            raise HTTPException(status_code=403, detail="administrator credential required")
        return auth

    def require_scope(required_scope: str):
        def guard(auth: AuthContext = Depends(authenticate)) -> AuthContext:
            if auth.is_admin:
                return auth
            assert auth.application is not None
            if not auth.application.allows(required_scope):
                raise HTTPException(status_code=403, detail=f"missing scope: {required_scope}")
            return auth
        return guard

    def scope_from(model: ScopeModel, auth: AuthContext) -> MemoryScope:
        application_id = model.application_id
        if not auth.is_admin:
            assert auth.application is not None
            if application_id is not None and application_id != auth.application.application_id:
                raise HTTPException(status_code=403, detail="application credential cannot access another application scope")
            application_id = auth.application.application_id
        return MemoryScope(
            service.organization.organization_id,
            application_id=application_id,
            agent_id=model.agent_id,
            user_id=model.user_id,
        )

    def persist() -> None:
        if persist_root is not None:
            service.save(persist_root)

    @app.get(f"{API_PREFIX}/health")
    def health():
        return {"status": "ok", "product": "memoria.ia-enterprise", "maturity": "product-alpha"}

    @app.get(f"{API_PREFIX}/admin/status", dependencies=[Depends(require_admin)])
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
        applications = []
        if application_registry is not None:
            applications = [
                {
                    "application_id": record.application_id,
                    "display_name": record.display_name,
                    "scopes": sorted(record.scopes),
                    "enabled": record.enabled,
                    "created_at": record.created_at.isoformat(),
                }
                for record in application_registry.list()
            ]
        return {
            "organization": {
                "organization_id": service.organization.organization_id,
                "display_name": service.organization.display_name,
            },
            "node": identity,
            "memory": service.statistics,
            "llm": llm,
            "applications": applications,
            "semantic_routing": "experimental",
            "security_status": "not-security-reviewed",
        }

    @app.get(f"{API_PREFIX}/admin/applications", dependencies=[Depends(require_admin)])
    def list_applications():
        if application_registry is None:
            return {"applications": []}
        return {
            "applications": [
                {
                    "application_id": record.application_id,
                    "display_name": record.display_name,
                    "scopes": sorted(record.scopes),
                    "enabled": record.enabled,
                    "created_at": record.created_at.isoformat(),
                }
                for record in application_registry.list()
            ]
        }

    @app.post(f"{API_PREFIX}/admin/applications", status_code=201, dependencies=[Depends(require_admin)])
    def create_application(request: CreateApplicationRequest):
        if application_registry is None:
            raise HTTPException(status_code=503, detail="application registry is not configured")
        try:
            created = application_registry.create(
                request.application_id,
                display_name=request.display_name,
                scopes=request.scopes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "application": {
                "application_id": created.record.application_id,
                "display_name": created.record.display_name,
                "scopes": sorted(created.record.scopes),
                "enabled": created.record.enabled,
            },
            "credential": created.token,
            "credential_notice": "This credential is returned once. Store it securely; Memoria.ia persists only a verifier.",
        }

    @app.delete(f"{API_PREFIX}/admin/applications/{{application_id}}", dependencies=[Depends(require_admin)])
    def revoke_application(application_id: str):
        if application_registry is None:
            raise HTTPException(status_code=503, detail="application registry is not configured")
        try:
            record = application_registry.revoke(application_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="application not found") from exc
        return {"application_id": record.application_id, "enabled": record.enabled}

    @app.post(f"{API_PREFIX}/memories", status_code=201)
    def store_memory(request: StoreMemoryRequest, auth: AuthContext = Depends(require_scope("memory.write"))):
        scope = scope_from(request.scope, auth)
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

    @app.put(f"{API_PREFIX}/memories/{{key}}")
    def update_memory(key: str, request: UpdateMemoryRequest, auth: AuthContext = Depends(require_scope("memory.write"))):
        scope = scope_from(request.scope, auth)
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

    @app.delete(f"{API_PREFIX}/memories/{{key}}")
    def revoke_memory(
        key: str,
        application_id: str | None = None,
        agent_id: str | None = None,
        user_id: str | None = None,
        auth: AuthContext = Depends(require_scope("memory.write")),
    ):
        scope = scope_from(ScopeModel(application_id=application_id, agent_id=agent_id, user_id=user_id), auth)
        try:
            service.revoke(scope, ("key", key))
            persist()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"revoked": True, "key": key}

    @app.post(f"{API_PREFIX}/memories/resolve")
    def resolve_memory(request: ResolveMemoryRequest, auth: AuthContext = Depends(require_scope("memory.read"))):
        scope = scope_from(request.scope, auth)
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

    @app.post(f"{API_PREFIX}/chat")
    def chat(request: ChatRequest, auth: AuthContext = Depends(require_scope("chat.use"))):
        if chat_service is None:
            raise HTTPException(status_code=503, detail="LLM adapter is not configured")
        try:
            result = chat_service.run(
                scope=scope_from(request.scope, auth),
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

    @app.post(f"{API_PREFIX}/chat/compare")
    def compare_chat(request: CompareChatRequest, auth: AuthContext = Depends(require_scope("chat.use"))):
        if chat_service is None:
            raise HTTPException(status_code=503, detail="LLM adapter is not configured")
        scope = scope_from(request.scope, auth)
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
