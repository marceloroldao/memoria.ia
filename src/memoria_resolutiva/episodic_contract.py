from __future__ import annotations

from dataclasses import dataclass
import hmac
from typing import Protocol

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field


@dataclass(frozen=True, slots=True)
class EpisodicRecallResult:
    status: str
    confidence: float
    episode_ids: tuple[str, ...]
    selected_context: str
    order: int | None
    timestamp: str | None
    event_type: str | None
    topics: tuple[str, ...]
    source_type: str | None = None
    source_authority: float | None = None
    ultimate_source_memory_id: str | None = None


class EpisodeStoreRequest(BaseModel):
    episode_id: str = Field(min_length=1, max_length=256)
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(min_length=1, max_length=20000)
    session_id: str | None = Field(default=None, max_length=256)
    order: int = Field(ge=0)
    timestamp: str | None = Field(default=None, max_length=128)
    event_type: str | None = Field(default=None, max_length=128)
    topics: list[str] = Field(default_factory=list)
    parent_memory_ids: list[str] = Field(default_factory=list)


class EpisodeRecallRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=256)
    role: str | None = Field(default=None, pattern="^(user|assistant)$")
    event_type: str | None = Field(default=None, max_length=128)
    topics: list[str] = Field(default_factory=list)


class EpisodicService(Protocol):
    def store(self, request: EpisodeStoreRequest): ...

    def resolve(self, request: EpisodeRecallRequest): ...

    def history(
        self,
        *,
        session_id: str | None = None,
        event_type: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, object]]: ...


def attach_episodic_routes(app: FastAPI, *, api_key: str, service: EpisodicService) -> None:
    """Attach the stable episodic HTTP contract without selecting an implementation."""

    def require_admin(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    @app.post("/api/v1/episodes", status_code=201, dependencies=[Depends(require_admin)])
    def store_episode(request: EpisodeStoreRequest):
        try:
            edge, receipt = service.store(request)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "stored": True,
            "episode_id": edge.evidence_id,
            "namespace": edge.namespace,
            "persistence": receipt.as_dict(),
        }

    @app.get("/api/v1/episodes/history", dependencies=[Depends(require_admin)])
    def episode_history(
        session_id: str | None = Query(default=None, max_length=256),
        event_type: str | None = Query(default=None, max_length=128),
        limit: int = Query(default=1000, ge=1, le=5000),
    ):
        try:
            episodes = service.history(session_id=session_id, event_type=event_type, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "schema": "memoria-episode-history/v1",
            "session_id": session_id,
            "event_type": event_type,
            "count": len(episodes),
            "episodes": episodes,
        }

    @app.post("/api/v1/episodes/recall", dependencies=[Depends(require_admin)])
    def recall_episode(request: EpisodeRecallRequest):
        try:
            result = service.resolve(request)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "status": result.status,
            "confidence": round(result.confidence, 6),
            "episode_ids": list(result.episode_ids),
            "selected_context": result.selected_context,
            "order": result.order,
            "timestamp": result.timestamp,
            "event_type": result.event_type,
            "topics": list(result.topics),
            "source_type": result.source_type,
            "source_authority": result.source_authority,
            "ultimate_source_memory_id": result.ultimate_source_memory_id,
        }
