from __future__ import annotations

import hashlib
import hmac
import json
from typing import Protocol

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .episodic_contract import EpisodeStoreRequest


STRUCTURAL_SCHEMA = "memoria-structural-observation/v1"
STRUCTURAL_EVENT_TYPE = "structural_observation"
MAX_STRUCTURAL_TEXT_BYTES = 18_000


class StructuralObservationRequest(BaseModel):
    hierarchy_id: str = Field(min_length=1, max_length=256)
    source_id: str = Field(min_length=1, max_length=256)
    sequence: int = Field(ge=0)
    byte_offset: int = Field(ge=0)
    byte_length: int = Field(ge=0)
    signature: str = Field(min_length=1, max_length=256)
    resolution: int = Field(ge=1, le=32)
    relation_ids: list[int] = Field(default_factory=list)
    trail_symbols: int = Field(default=0, ge=0)
    content_sha256: str | None = Field(default=None, max_length=64)
    content_type: str | None = Field(default=None, max_length=256)
    observed_at: str | None = Field(default=None, max_length=128)
    url: str | None = Field(default=None, max_length=4096)
    checkpoint_file: str | None = Field(default=None, max_length=256)


class StructuralEpisodeSink(Protocol):
    def store_structural(self, request: EpisodeStoreRequest): ...


def _canonical_payload(request: StructuralObservationRequest) -> tuple[str, str, str]:
    if len(request.relation_ids) > 4096:
        raise ValueError("relation_ids exceeds structural observation limit")
    if any(int(value) < 256 for value in request.relation_ids):
        raise ValueError("relation_ids must contain relation symbols >= 256")
    if request.content_sha256 is not None:
        digest = request.content_sha256.casefold()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("content_sha256 must be a 64-character hexadecimal digest")

    payload = {
        "schema": STRUCTURAL_SCHEMA,
        "hierarchy_id": request.hierarchy_id,
        "source_id": request.source_id,
        "sequence": request.sequence,
        "byte_offset": request.byte_offset,
        "byte_length": request.byte_length,
        "signature": request.signature,
        "resolution": request.resolution,
        "relation_ids": [int(value) for value in request.relation_ids],
        "trail_symbols": request.trail_symbols,
        "content_sha256": request.content_sha256.casefold() if request.content_sha256 else None,
        "content_type": request.content_type,
        "observed_at": request.observed_at,
        "url": request.url,
        "checkpoint_file": request.checkpoint_file,
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(text.encode("utf-8")) > MAX_STRUCTURAL_TEXT_BYTES:
        raise ValueError("structural observation exceeds native episodic payload limit")

    episode_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:40]
    session_digest = hashlib.sha256(
        (request.hierarchy_id + "\0" + request.source_id).encode("utf-8")
    ).hexdigest()[:40]
    return text, f"structural:{episode_digest}", f"structural:{session_digest}"


def attach_structural_routes(
    app: FastAPI,
    *,
    api_key: str,
    service: StructuralEpisodeSink | None,
) -> None:
    def require_admin(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    @app.post("/api/v1/structural/events", status_code=201, dependencies=[Depends(require_admin)])
    def store_structural_event(request: StructuralObservationRequest):
        if service is None:
            raise HTTPException(status_code=503, detail="structural observation journal is unavailable")
        try:
            text, episode_id, session_id = _canonical_payload(request)
            edge, receipt = service.store_structural(EpisodeStoreRequest(
                episode_id=episode_id,
                role="assistant",
                text=text,
                session_id=session_id,
                order=request.sequence,
                timestamp=request.observed_at,
                event_type=STRUCTURAL_EVENT_TYPE,
                topics=[],
            ))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "stored": True,
            "episode_id": edge.evidence_id,
            "hierarchy_id": request.hierarchy_id,
            "source_id": request.source_id,
            "sequence": request.sequence,
            "persistence": receipt.as_dict(),
        }
