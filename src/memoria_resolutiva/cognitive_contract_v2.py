from __future__ import annotations

import hmac
from typing import Protocol

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .cognitive_abi_v2 import CognitiveAbiEnvelopeV2
from .context_compiler_v2 import ContextCompilerV2
from .resolutive_inference_v2 import ResolutiveInferenceEngineV2


class CognitiveResolveRequestV2(BaseModel):
    request_id: str = Field(min_length=1, max_length=256)
    hierarchy_id: str = Field(min_length=1, max_length=256)
    addresses: list[int] = Field(min_length=1, max_length=4096)
    session_id: str | None = Field(default=None, max_length=256)


class CognitiveAbiResolverV2(Protocol):
    def resolve(
        self,
        *,
        request_id: str,
        hierarchy_id: str,
        addresses: tuple[int, ...] | list[int],
        session_id: str | None = None,
    ) -> CognitiveAbiEnvelopeV2: ...


class StructuralCognitiveAbiServiceV2:
    """Zero-LLM server adapter over the reconciled structural inference engine."""

    def __init__(self, engine: ResolutiveInferenceEngineV2) -> None:
        self.engine = engine

    def resolve(
        self,
        *,
        request_id: str,
        hierarchy_id: str,
        addresses: tuple[int, ...] | list[int],
        session_id: str | None = None,
    ) -> CognitiveAbiEnvelopeV2:
        result = self.engine.infer_structural(
            addresses,
            hierarchy_id=hierarchy_id,
        )
        packet = ContextCompilerV2.compile_structural(result)
        return CognitiveAbiEnvelopeV2.from_context(
            packet,
            request_id=request_id,
            session_id=session_id,
            execution_plane="server",
            memory_plane="server",
            language_plane="none",
        )


def attach_cognitive_routes_v2(
    app: FastAPI,
    *,
    api_key: str,
    service: CognitiveAbiResolverV2,
) -> None:
    """Attach an admin-protected structural ABI transport.

    This transport is intentionally address-level. Natural-language interpretation
    and application-scoped authorization belong to later integration adapters.
    """

    if not api_key:
        raise ValueError("api_key must be configured")

    def require_admin(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    @app.post(
        "/api/v1/cognitive/resolve",
        dependencies=[Depends(require_admin)],
    )
    def resolve_cognitive(request: CognitiveResolveRequestV2):
        try:
            envelope = service.resolve(
                request_id=request.request_id,
                hierarchy_id=request.hierarchy_id,
                addresses=request.addresses,
                session_id=request.session_id,
            )
        except (ValueError, LookupError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return envelope.as_dict()
