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
            raise HTTPException(status_code=403, detail="administrator credentials required")
        return auth

    def scope_from_request(scope: ScopeModel, auth: AuthContext):
        application_id = scope.application_id
        if auth.application is not None:
            if application_id is not None and application_id != auth.application.application_id:
                raise HTTPException(status_code=403, detail="application scope mismatch")
            application_id = auth.application.application_id
        return service.scope(
            application_id=application_id,
            agent_id=scope.agent_id,
            user_id=scope.user_id,
        )

    @app.get(f"{API_PREFIX}/health")
    def health():
        return service.health(node_identity=node_identity)

    @app.post(f"{API_PREFIX}/memory/store", dependencies=[Depends(authenticate)])
    def store(request: StoreMemoryRequest, auth: AuthContext = Depends(authenticate)):
        if auth.application is not None and "memory.write" not in auth.application.scopes:
            raise HTTPException(status_code=403, detail="memory.write scope required")
        scope = scope_from_request(request.scope, auth)
        try:
            return service.store(
                request.knowledge_id,
                request.key,
                request.payload,
                scope,
                modality=request.modality,
                provenance=request.provenance,
            )
        except OrganizationMismatch as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(f"{API_PREFIX}/memory/resolve", dependencies=[Depends(authenticate)])
    def resolve(request: ResolveMemoryRequest, auth: AuthContext = Depends(authenticate)):
        if auth.application is not None and "memory.read" not in auth.application.scopes:
            raise HTTPException(status_code=403, detail="memory.read scope required")
        scope = scope_from_request(request.scope, auth)
        try:
            return service.resolve(
                request.key,
                scope,
                include_revoked=request.include_revoked,
                version=request.version,
            )
        except (OrganizationMismatch, MemoryRevoked) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(f"{API_PREFIX}/memory/update", dependencies=[Depends(authenticate)])
    def update(request: UpdateMemoryRequest, auth: AuthContext = Depends(authenticate)):
        if auth.application is not None and "memory.write" not in auth.application.scopes:
            raise HTTPException(status_code=403, detail="memory.write scope required")
        scope = scope_from_request(request.scope, auth)
        try:
            return service.update(
                request.payload,
                scope,
                modality=request.modality,
                provenance=request.provenance,
            )
        except OrganizationMismatch as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(f"{API_PREFIX}/memory/{{knowledge_id}}", dependencies=[Depends(authenticate)])
    def retrieve(knowledge_id: str, auth: AuthContext = Depends(authenticate)):
        if auth.application is not None and "memory.read" not in auth.application.scopes:
            raise HTTPException(status_code=403, detail="memory.read scope required")
        return service.retrieve(knowledge_id)

    @app.delete(f"{API_PREFIX}/memory/{{knowledge_id}}", dependencies=[Depends(authenticate)])
    def delete(knowledge_id: str, auth: AuthContext = Depends(authenticate)):
        if auth.application is not None and "memory.write" not in auth.application.scopes:
            raise HTTPException(status_code=403, detail="memory.write scope required")
        return service.delete(knowledge_id)

    @app.post(f"{API_PREFIX}/chat", dependencies=[Depends(authenticate)])
    def chat(request: ChatRequest, auth: AuthContext = Depends(authenticate)):
        if chat_service is None:
            raise HTTPException(status_code=503, detail="LLM provider is not configured")
        if auth.application is not None and "chat.use" not in auth.application.scopes:
            raise HTTPException(status_code=403, detail="chat.use scope required")
        scope = scope_from_request(request.scope, auth)
        try:
            return chat_service.chat(
                request.message,
                mode=request.mode,
                baseline_context=request.baseline_context,
                memory_keys=request.memory_keys,
                scope=scope,
            )
        except LLMAdapterError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post(f"{API_PREFIX}/chat/compare", dependencies=[Depends(authenticate)])
    def compare_chat(request: CompareChatRequest, auth: AuthContext = Depends(authenticate)):
        if chat_service is None:
            raise HTTPException(status_code=503, detail="LLM provider is not configured")
        if auth.application is not None and "chat.use" not in auth.application.scopes:
            raise HTTPException(status_code=403, detail="chat.use scope required")
        scope = scope_from_request(request.scope, auth)
        try:
            baseline = chat_service.chat(
                request.message,
                mode="baseline",
                baseline_context=request.baseline_context,
                memory_keys=request.memory_keys,
                scope=scope,
            )
            memoria = chat_service.chat(
                request.message,
                mode="memoria",
                baseline_context=request.baseline_context,
                memory_keys=request.memory_keys,
                scope=scope,
            )
        except LLMAdapterError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {
            "baseline": baseline,
            "memoria": memoria,
            "token_reduction": token_reduction(baseline, memoria),
        }

    @app.post(f"{API_PREFIX}/applications", dependencies=[Depends(require_admin)])
    def create_application(request: CreateApplicationRequest):
        if application_registry is None:
            raise HTTPException(status_code=503, detail="application registry is not configured")
        return application_registry.create(
            request.application_id,
            display_name=request.display_name,
            scopes=frozenset(request.scopes),
        )

    @app.get(f"{API_PREFIX}/applications", dependencies=[Depends(require_admin)])
    def list_applications():
        if application_registry is None:
            raise HTTPException(status_code=503, detail="application registry is not configured")
        return application_registry.list()

    return app
