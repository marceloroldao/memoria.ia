from __future__ import annotations

import hmac

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .episodic_recall import Episode, EpisodicRecallService
from .product_evidence import ProductEvidenceService


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


class ProductEpisodicService:
    def __init__(self, evidence: ProductEvidenceService) -> None:
        self.evidence = evidence
        self.recall = EpisodicRecallService(evidence.core)

    def store(self, request: EpisodeStoreRequest):
        edge = self.recall.record(Episode(
            request.episode_id,
            request.role,
            request.text,
            request.session_id,
            request.order,
            request.timestamp,
            request.event_type,
            tuple(request.topics),
            tuple(request.parent_memory_ids),
        ))
        receipt = self.evidence.save()
        return edge, receipt

    def resolve(self, request: EpisodeRecallRequest):
        return self.recall.recall_latest(
            query=request.query,
            namespace=request.session_id,
            role=request.role,
            event_type=request.event_type,
            topics=tuple(request.topics),
        )


def attach_episodic_routes(app: FastAPI, *, api_key: str, service: ProductEpisodicService) -> None:
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

    @app.post("/api/v1/episodes/recall", dependencies=[Depends(require_admin)])
    def recall_episode(request: EpisodeRecallRequest):
        try:
            result = service.resolve(request)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "status": result.status,
            "confidence": result.confidence,
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
