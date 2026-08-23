from __future__ import annotations

from pathlib import Path
import os

from .llm_adapter import MockLLMAdapter
from .product_chat import ProductChatService
from .product_http import create_app
from .product_identity import OrganizationIdentity, NodeIdentity, CertificateStatus, LicenseStatus
from .product_service import EnterpriseMemoryService


def _env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and (value is None or value == ""):
        raise RuntimeError(f"required environment variable {name} is not configured")
    assert value is not None
    return value


def _build_chat_service(memory: EnterpriseMemoryService) -> ProductChatService | None:
    provider = os.getenv("MEMORIA_LLM_PROVIDER", "").strip().lower()
    if not provider:
        return None
    if provider == "mock":
        return ProductChatService(memory, MockLLMAdapter())
    raise RuntimeError(f"unsupported MEMORIA_LLM_PROVIDER: {provider}")


def build_app():
    organization_id = _env("MEMORIA_ORGANIZATION_ID", required=True)
    organization_name = os.getenv("MEMORIA_ORGANIZATION_NAME")
    api_key = _env("MEMORIA_API_KEY", required=True)
    data_dir = Path(_env("MEMORIA_DATA_DIR", "/data"))

    manifest = data_dir / "enterprise.manifest.json"
    if manifest.exists():
        service = EnterpriseMemoryService.load(data_dir)
        if service.organization.organization_id != organization_id:
            raise RuntimeError("persisted organization does not match MEMORIA_ORGANIZATION_ID")
    else:
        service = EnterpriseMemoryService(OrganizationIdentity(organization_id, organization_name))

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

    return create_app(
        service,
        api_key=api_key,
        data_dir=data_dir,
        node_identity=node_identity,
        chat_service=_build_chat_service(service),
    )


app = build_app()
