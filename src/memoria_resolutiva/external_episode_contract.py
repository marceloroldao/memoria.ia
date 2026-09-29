"""Versioned receipt for Live.infinita witnessed non-conversational episodes.

The existing Product EvidenceCore persists immutable source-backed observations.
This route never converts Nov to role=user/assistant, infers missing content, or
obtains authority over World State.
"""
from __future__ import annotations

from hashlib import sha256
import hmac
import json
from threading import RLock
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .product_evidence import ProductEvidenceService

FORMAT = "live-infinita-npc-episode-observation/v1"
PROVENANCE = "live.infinita:npc_episode_v1"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


class EpisodeSource(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    system: Literal["live.infinita"]
    world_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")
    entity_id: Literal["nov"]
    episode_id: str = Field(min_length=1, max_length=160, pattern=r"^plan:[A-Za-z0-9._:-]+$")
    source_schema: Literal["npc_episode_v1"]
    source_kind: Literal["need_outcome"]
    plan_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")
    proposal_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")
    plan_revision: int = Field(ge=0, le=1_000_000)


class EpisodeContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    period: str | None = Field(max_length=96)
    weather: str | None = Field(max_length=96)
    region_id: str | None = Field(max_length=128)
    danger_level: float | None = Field(ge=0.0, le=1.0)


class EpisodeOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    satisfaction: float | None = Field(ge=0.0, le=1.0)
    observed_risk: float | None = Field(ge=0.0, le=1.0)
    elapsed_ticks: int | None = Field(ge=0, le=10**12)
    preemptions: int | None = Field(ge=0, le=10**12)
    replans: int | None = Field(ge=0, le=10**12)


class EpisodeObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    logical_tick: int = Field(ge=0, le=10**12)
    need: str | None = Field(max_length=96)
    target_entity_id: str | None = Field(max_length=128)
    strategy_id: str | None = Field(max_length=128)
    context: EpisodeContext
    outcome: EpisodeOutcome


class ExternalEpisodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema: Literal["live-infinita-npc-episode-observation/v1"]
    record_key: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    source: EpisodeSource
    observation: EpisodeObservation
    authority: Literal["observed-outcome-only"]
    world_write_authority: Literal[False]
    content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


def attach_external_episode_routes(app: FastAPI, *, api_key: str, evidence: ProductEvidenceService, incremental=None) -> None:
    """ACK is returned only after a durable snapshot, retry idempotent by source."""
    lock = RLock()
    # Scoped acceleration only; the persisted graph is re-read after restart.
    cache: dict[tuple[str, str], object] = {}
    pending: set[tuple[str, str]] = set()

    def require_admin(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    @app.post("/api/v1/external/episodes", status_code=201, dependencies=[Depends(require_admin)])
    def ingest_external_episode(request: ExternalEpisodeRequest):
        source = request.source
        if source.episode_id != "plan:" + source.plan_id:
            raise HTTPException(status_code=422, detail="episode plan provenance mismatch")
        identity = {
            "system": source.system, "world_id": source.world_id,
            "entity_id": source.entity_id, "episode_id": source.episode_id,
        }
        record_key = sha256(canonical(identity)).hexdigest()
        if not hmac.compare_digest(record_key, request.record_key):
            raise HTTPException(status_code=422, detail="record identity mismatch")
        unsigned = request.model_dump(mode="json", exclude={"content_sha256"})
        content_sha256 = sha256(canonical(unsigned)).hexdigest()
        if not hmac.compare_digest(content_sha256, request.content_sha256):
            raise HTTPException(status_code=422, detail="observation digest mismatch")
        if incremental is not None:
            try:
                return incremental.observe(request)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            # Runtime/storage errors are deliberately not converted into ACKs.
        namespace = "live:" + source.world_id
        evidence_id = "live-obs:" + record_key[:40]
        source_payload = canonical(unsigned).decode("utf-8")
        subject = "live:episode:" + evidence_id
        object_id = "live:entity:" + source.world_id + ":" + source.entity_id
        key = (namespace, evidence_id)
        with lock:
            existing = cache.get(key)
            if existing is None:
                matches = [
                    row for row in evidence.core.evidence_history(namespace=namespace)
                    if row.evidence_id == evidence_id
                ]
                if len(matches) > 1:
                    raise HTTPException(status_code=409, detail="conflicting duplicate episode history")
                existing = matches[0] if matches else None
                if existing is not None:
                    cache[key] = existing
            if existing is not None:
                if not (
                    existing.subject == subject
                    and existing.predicate == "observed_experience"
                    and existing.object == object_id
                    and existing.source_text == source_payload
                    and existing.provenance == PROVENANCE
                    and existing.origin == f"live.infinita:{source.world_id}"
                    and existing.epoch == request.observation.logical_tick
                ):
                    raise HTTPException(status_code=409, detail="episode identity reused with different observed content")
                if key in pending or evidence.receipt is None:
                    receipt = evidence.save()
                    pending.discard(key)
                else:
                    receipt = evidence.receipt
                stored = False
            else:
                edge = evidence.core.observe_relation(
                    subject, "observed_experience", object_id,
                    evidence_id=evidence_id,
                    source_text=source_payload,
                    provenance=PROVENANCE,
                    origin=f"live.infinita:{source.world_id}",
                    confidence=1.0,
                    namespace=namespace,
                    epoch=request.observation.logical_tick,
                )
                cache[key] = edge
                pending.add(key)
                receipt = evidence.save()
                pending.discard(key)
                stored = True
        return {
            "schema": FORMAT,
            "ack": True,
            "stored": stored,
            "record_key": record_key,
            "episode_id": source.episode_id,
            "evidence_id": evidence_id,
            "content_sha256": content_sha256,
            "world_id": source.world_id,
            "persistence": receipt.as_dict(),
            "world_mutated": False,
            "selection_authority": False,
        }
    @app.get("/api/v1/external/episodes/health", dependencies=[Depends(require_admin)])
    def incremental_external_episode_health():
        return {
            "status": "ok",
            "mode": "sqlite-incremental" if incremental is not None else "snapshot",
            "observations": incremental.count if incremental is not None else None,
            "world_mutated": False,
            "selection_authority": False,
        }

