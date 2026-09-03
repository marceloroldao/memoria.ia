from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import os

from .conversation_contract import attach_conversation_routes
from .conversation_episodic_bridge import AutoEpisodicConversationService
from .episodic_contract import attach_episodic_routes
from .gemini_adapter import GeminiGenerateContentAdapter, GeminiPricing
from .llm_adapter import MockLLMAdapter
from .native_conversation import NativeConversationService
from .native_episodic import NativeEpisodicService
from .openai_adapter import OpenAIPricing, OpenAIResponsesAdapter
from .product_admin_config import attach_configuration_routes
from .product_applications import ApplicationRegistry
from .product_chat import ProductChatService
from .product_config import ProductConfigurationStore
from .product_evidence import ProductEvidenceService, attach_evidence_routes
from .product_http import create_app
from .product_identity import OrganizationIdentity, NodeIdentity, CertificateStatus, LicenseStatus
from .product_persistence import ProductSnapshotPersistence, PersistentEnterpriseMemoryService
from .product_service import EnterpriseMemoryService


def _env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and (value is None or value == ""):
        raise RuntimeError(f"required environment variable {name} is not configured")
    assert value is not None
    return value


def _optional_float(name: str) -> float | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return float(value)


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"environment variable {name} must be a boolean value")


def _build_chat_service(
    memory: EnterpriseMemoryService,
    configuration: ProductConfigurationStore,
    *,
    conversation_resolver=None,
) -> ProductChatService | None:
    persisted = configuration.llm()
    provider = os.getenv("MEMORIA_LLM_PROVIDER", persisted.provider or "").strip().lower()
    if not provider:
        return None
    if provider == "mock":
        return ProductChatService(memory, MockLLMAdapter(), conversation_resolver=conversation_resolver)

    model = os.getenv("MEMORIA_LLM_MODEL", persisted.model or "").strip()
    if not model:
        raise RuntimeError("MEMORIA_LLM_MODEL is required for an external provider")

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", persisted.api_key or "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI")
        adapter = OpenAIResponsesAdapter(
            api_key=api_key,
            model=model,
            base_url=_env("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            pricing=OpenAIPricing(
                input_usd_per_million=_optional_float("MEMORIA_LLM_INPUT_USD_PER_MILLION"),
                output_usd_per_million=_optional_float("MEMORIA_LLM_OUTPUT_USD_PER_MILLION"),
            ),
        )
        return ProductChatService(memory, adapter, conversation_resolver=conversation_resolver)
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", persisted.api_key or "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini")
        adapter = GeminiGenerateContentAdapter(
            api_key=api_key,
            model=model,
            base_url=_env("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"),
            pricing=GeminiPricing(
                input_usd_per_million=_optional_float("MEMORIA_LLM_INPUT_USD_PER_MILLION"),
                output_usd_per_million=_optional_float("MEMORIA_LLM_OUTPUT_USD_PER_MILLION"),
            ),
        )
        return ProductChatService(memory, adapter, conversation_resolver=conversation_resolver)
    raise RuntimeError(f"unsupported MEMORIA_LLM_PROVIDER: {provider}")


def _native_library_path(runtime_name: str) -> str:
    library_path = os.getenv("MEMORIA_NATIVE_LIB", "").strip()
    if not library_path:
        raise RuntimeError(f"MEMORIA_NATIVE_LIB is required when {runtime_name}=native")
    return library_path


def _build_conversation_service(
    *,
    evidence_service: ProductEvidenceService,
    data_dir: Path,
    organization_id: str,
    native_data_dir: Path | None = None,
):
    runtime = os.getenv("MEMORIA_CONVERSATION_RUNTIME", "native").strip().lower()
    if runtime == "python":
        from .reference_conversation import ConversationSemanticService

        return ConversationSemanticService(evidence_service)
    if runtime != "native":
        raise RuntimeError("MEMORIA_CONVERSATION_RUNTIME must be 'python' or 'native'")
    return NativeConversationService(
        library_path=_native_library_path("MEMORIA_CONVERSATION_RUNTIME"),
        data_dir=native_data_dir or (data_dir / "native-conversation"),
        organization_id=organization_id,
    )


def _build_episodic_service(
    *,
    evidence_service: ProductEvidenceService,
    data_dir: Path,
    organization_id: str,
    native_data_dir: Path | None = None,
):
    runtime = os.getenv("MEMORIA_EPISODIC_RUNTIME", "native").strip().lower()
    if runtime == "python":
        from .reference_episodic import ProductEpisodicService

        return ProductEpisodicService(evidence_service)
    if runtime != "native":
        raise RuntimeError("MEMORIA_EPISODIC_RUNTIME must be 'python' or 'native'")
    return NativeEpisodicService(
        library_path=_native_library_path("MEMORIA_EPISODIC_RUNTIME"),
        data_dir=native_data_dir or (data_dir / "native-episodic"),
        organization_id=organization_id,
    )


def _native_shared_data_dir(data_dir: Path) -> Path | None:
    conversation_runtime = os.getenv("MEMORIA_CONVERSATION_RUNTIME", "native").strip().lower()
    episodic_runtime = os.getenv("MEMORIA_EPISODIC_RUNTIME", "native").strip().lower()
    if conversation_runtime != "native" or episodic_runtime != "native":
        return None
    legacy_paths = (data_dir / "native-conversation", data_dir / "native-episodic")
    legacy_with_state = [path for path in legacy_paths if path.exists() and any(path.iterdir())]
    if legacy_with_state:
        names = ", ".join(str(path) for path in legacy_with_state)
        raise RuntimeError(
            "legacy split native stores contain data and require explicit migration before enabling both native runtimes: " + names
        )
    return data_dir / "native-runtime"


def build_app():
    organization_id = _env("MEMORIA_ORGANIZATION_ID", required=True)
    organization_name = os.getenv("MEMORIA_ORGANIZATION_NAME")
    api_key = _env("MEMORIA_API_KEY", required=True)
    data_dir = Path(_env("MEMORIA_DATA_DIR", "/data"))
    configuration = ProductConfigurationStore(data_dir)
    storage_backend = os.getenv("MEMORIA_STORAGE_BACKEND")
    storage_allow_fallback = _env_bool("MEMORIA_STORAGE_ALLOW_FALLBACK", True)
    persistence = ProductSnapshotPersistence(
        data_dir / "persistence",
        backend=storage_backend,
        allow_fallback=storage_allow_fallback,
    )

    manifest = data_dir / "enterprise.manifest.json"
    if manifest.exists():
        service = PersistentEnterpriseMemoryService.load(data_dir, persistence=persistence)
        if service.organization.organization_id != organization_id:
            raise RuntimeError("persisted organization does not match MEMORIA_ORGANIZATION_ID")
    else:
        service = PersistentEnterpriseMemoryService(
            OrganizationIdentity(organization_id, organization_name),
            persistence=persistence,
        )

    evidence_service = ProductEvidenceService.open(
        data_dir / "evidence",
        backend=storage_backend,
        allow_fallback=storage_allow_fallback,
    )
    native_shared_data_dir = _native_shared_data_dir(data_dir)
    conversation_backend = _build_conversation_service(
        evidence_service=evidence_service,
        data_dir=data_dir,
        organization_id=organization_id,
        native_data_dir=native_shared_data_dir,
    )
    episodic_service = _build_episodic_service(
        evidence_service=evidence_service,
        data_dir=data_dir,
        organization_id=organization_id,
        native_data_dir=native_shared_data_dir,
    )
    conversation_service = AutoEpisodicConversationService(conversation_backend, episodic_service)

    node_id = _env("MEMORIA_NODE_ID", f"memoria:{organization_id}:primary")
    node_identity = NodeIdentity(
        organization_id=organization_id,
        node_id=node_id,
        public_key=os.getenv("MEMORIA_PUBLIC_KEY"),
        certificate_ref=os.getenv("MEMORIA_CERTIFICATE_REF"),
        certificate_status=CertificateStatus(os.getenv("MEMORIA_CERTIFICATE_STATUS", "not_configured")),
        license_status=LicenseStatus(os.getenv("MEMORIA_LICENSE_STATUS", "not_configured")),
        capabilities=frozenset(filter(None, os.getenv("MEMORIA_CAPABILITIES", "memory.read,memory.write").split(","))),
    )

    application_registry = ApplicationRegistry(
        organization_id,
        data_dir / "applications.json",
    )

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            if isinstance(conversation_backend, NativeConversationService):
                conversation_backend.close()
            if isinstance(episodic_service, NativeEpisodicService):
                episodic_service.close()

    chat_service = _build_chat_service(
        service,
        configuration,
        conversation_resolver=conversation_service,
    )
    app = create_app(
        service,
        api_key=api_key,
        data_dir=data_dir,
        node_identity=node_identity,
        chat_service=chat_service,
        application_registry=application_registry,
        lifespan=lifespan,
    )

    @app.get("/api/v1/storage/health")
    def storage_health():
        stats = service.statistics
        return {
            "status": "ok",
            "backend": stats.get("persistence_backend", "unknown"),
            "portable_snapshot_fallback": bool(stats.get("portable_snapshot_fallback", False)),
            "evidence_backend": evidence_service.backend,
            "evidence_persisted": evidence_service.receipt is not None,
            "conversation_runtime": "native" if isinstance(conversation_backend, NativeConversationService) else "python",
            "episodic_runtime": "native" if isinstance(episodic_service, NativeEpisodicService) else "python",
            "automatic_episode_formation": True,
        }

    attach_evidence_routes(app, api_key=api_key, service=evidence_service)
    attach_conversation_routes(app, api_key=api_key, service=conversation_service)
    attach_episodic_routes(app, api_key=api_key, service=episodic_service)
    attach_configuration_routes(app, api_key=api_key, store=configuration)
    return app


app = build_app()
