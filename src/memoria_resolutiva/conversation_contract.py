from __future__ import annotations

from dataclasses import dataclass
import hmac
from typing import Protocol

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .memory_space import memory_space_for_source_type


@dataclass(frozen=True, slots=True)
class ConversationIngestResult:
    memory_ids: tuple[str, ...]
    relations: tuple[dict, ...]
    unresolved: bool


@dataclass(frozen=True, slots=True)
class ConversationResolveResult:
    status: str
    confidence: float
    memory_ids: tuple[str, ...]
    selected_context: str
    relations: tuple[dict, ...]
    provenance: tuple[dict, ...] = ()


class ConversationIngestRequest(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(min_length=1, max_length=20000)
    session_id: str | None = Field(default=None, max_length=256)
    timestamp: str | None = Field(default=None, max_length=128)
    order: int | None = Field(default=None, ge=0)
    parent_memory_ids: list[str] = Field(default_factory=list)
    corrects_memory_ids: list[str] = Field(default_factory=list)


class ConversationResolveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=256)


class ConversationService(Protocol):
    def ingest(
        self,
        *,
        role: str,
        text: str,
        session_id: str | None = None,
        order: int | None = None,
        timestamp: str | None = None,
        parent_memory_ids: tuple[str, ...] | list[str] = (),
        corrects_memory_ids: tuple[str, ...] | list[str] = (),
    ) -> ConversationIngestResult: ...

    def resolve(self, *, query: str, session_id: str | None = None) -> ConversationResolveResult: ...


def _provenance_with_memory_space(row: dict) -> dict:
    """Add epistemic-space metadata without breaking existing provenance fields."""
    payload = dict(row)
    ultimate_type = str(payload.get("source_type") or "retrieved_replay")
    immediate_type = str(payload.get("immediate_source_type") or ultimate_type)
    payload["memory_space"] = memory_space_for_source_type(immediate_type).value
    payload["ultimate_memory_space"] = memory_space_for_source_type(ultimate_type).value
    return payload


def attach_conversation_routes(app: FastAPI, *, api_key: str, service: ConversationService) -> None:
    """Attach the stable HTTP contract without importing a semantic implementation."""

    def require_admin(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    @app.post("/api/v1/conversation/ingest", dependencies=[Depends(require_admin)])
    def ingest(request: ConversationIngestRequest):
        try:
            result = service.ingest(
                role=request.role,
                text=request.text,
                session_id=request.session_id,
                timestamp=request.timestamp,
                order=request.order,
                parent_memory_ids=request.parent_memory_ids,
                corrects_memory_ids=request.corrects_memory_ids,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "stored_memory_ids": list(result.memory_ids),
            "relations": list(result.relations),
            "unresolved": result.unresolved,
        }

    @app.post("/api/v1/conversation/resolve", dependencies=[Depends(require_admin)])
    def resolve(request: ConversationResolveRequest):
        try:
            result = service.resolve(query=request.query, session_id=request.session_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "status": result.status,
            "confidence": result.confidence,
            "memory_ids": list(result.memory_ids),
            "selected_context": result.selected_context,
            "relations": list(result.relations),
            "provenance": [_provenance_with_memory_space(row) for row in result.provenance],
        }
