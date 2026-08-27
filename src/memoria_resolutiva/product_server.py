from __future__ import annotations

from pathlib import Path
import os

from .gemini_adapter import GeminiGenerateContentAdapter, GeminiPricing
from .llm_adapter import MockLLMAdapter
from .openai_adapter import OpenAIPricing, OpenAIResponsesAdapter
from .product_admin_config import attach_configuration_routes
from .product_applications import ApplicationRegistry
from .product_chat import ProductChatService
from .product_config import ProductConfigurationStore
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
) -> ProductChatService | None:
    persisted = configuration.llm()
    provider = os.getenv("MEMORIA_LLM_PROVIDER", persisted.provider or "").strip().lower()
    if not provider:
        return None
    if provider == "mock":
        return ProductChatService(memory, MockLLMAdapter())

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
        return ProductChatService(memory, adapter)
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
        return ProductChatService(memory, adapter)
    raise RuntimeError(f"unsupported MEMORIA_LLM_PROVIDER: {provider}")


def build_app():
    organization_id = _env("MEMORIA_ORGANIZATION_ID", required=True)
    organization_name = os.getenv("MEMORIA_ORGANIZATION_NAME")
    api_key = _env("MEMORIA_API_KEY", required=True)
    data_dir = Path(_env("MEMORIA_DATA_DIR", "/data"))
    configuration = ProductConfigurationStore(data_dir)
    persistence = ProductSnapshotPersistence(
        data_dir / "persistence",
        backend=os.getenv("MEMORIA_STORAGE_BACKEND"),
        allow_fallback=_env_bool("MEMORIA_STORAGE_ALLOW_FALLBACK", True),
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

    app = create_app(
        service,
        api_key=api_key,
        data_dir=data_dir,
        node_identity=node_identity,
        chat_service=_build_chat_service(service, configuration),
        application_registry=application_registry,
    )
    attach_configuration_routes(app, api_key=api_key, store=configuration)
    return app


app = build_app()
