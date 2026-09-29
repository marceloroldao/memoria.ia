"""Versioned ingress for witnessed, non-conversational episodes.

Events are observed evidence in the existing Product EvidenceCore, not synthetic
user turns, assistant output, or authority to mutate the source world.
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

FORMAT = "memoria.ia-external-episode/v1"
PROVENANCE = "live.infinita:npc_episode_v1"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


class EpisodeContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    period: str = Field(min_length=1, max_length=96)
    weather: str = Field(min_length=1, max_length=96)
    region_id: str = Field(min_length=1, max_length=128)
    danger_level: float = Field(ge=0.0, le=1.0)


class EpisodeOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    satisfaction: float = Field(ge=0.0, le=1.0)
    observed_risk: float = Field(ge=0.0, le=1.0)
    elapsed_ticks: int = Field(ge=0, le=10**12)
    preemptions: int = Field(ge=0, le=10**12)
    replans: int = Field(ge=0, le=10**12)


class WitnessedEpisode(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    episode_schema: Literal["npc_episode_v1"]
    episode_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")
    npc_id: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9._:-]+$")
    logical_tick: int = Field(ge=0, le=10**12)
    need: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9._:-]+$")
    target_entity_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    strategy_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    context: EpisodeContext
    outcome: EpisodeOutcome


class ExternalEpisodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema: Literal["memoria.ia-external-episode/v1"]
    source_system: Literal["live.infinita"]
    world_id: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9._:-]+$")
    episode: WitnessedEpisode
    episode_sha256: str = Field(min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")


def attach_external_episode_routes(app: FastAPI, *, api_key: str, evidence: ProductEvidenceService) -> None:
    """Idempotent durable receipt; source identity and bytes are immutable."""
    lock = RLock()
    # Only a process-local accelerator: scope is read from the persisted
    # EvidenceCore on first use and restored automatically after restart.
    cache: dict[tuple[str, str], object] = {}
    pending: set[tuple[str, str]] = set()

    def require_admin(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    @app.post("/api/v1/external/episodes", status_code=201, dependencies=[Depends(require_admin)])
    def ingest_external_episode(request: ExternalEpisodeRequest):
        observed = request.episode.model_dump(mode="json")
        digest = sha256(canonical(observed)).hexdigest()
        if not hmac.compare_digest(digest, request.episode_sha256):
            raise HTTPException(status_code=422, detail="episode content digest mismatch")
        namespace = "live:" + request.world_id
        seed = f"{request.world_id}\x00{request.episode.npc_id}\x00{request.episode.episode_id}"
        evidence_id = "live-obs:" + sha256(seed.encode("utf-8")).hexdigest()[:40]
        source_payload = canonical({
            "schema": FORMAT,
            "source_system": request.source_system,
            "world_id": request.world_id,
            "episode": observed,
        }).decode("utf-8")
        subject = "live:episode:" + evidence_id
        object_id = "live:entity:" + request.world_id + ":" + request.episode.npc_id
        key = (namespace, evidence_id)
        with lock:
            existing = cache.get(key)
            if existing is None:
                matches = [
                    row for row in evidence.core.evidence_history(namespace=namespace)
                    if row.evidence_id == evidence_id
                ]
                if len(matches) > 1:
                    raise HTTPException(status_code=409, detail="duplicate identity conflict in evidence history")
                existing = matches[0] if matches else None
                if existing is not None:
                    cache[key] = existing
            if existing is not None:
                if not (
                    existing.subject == subject and existing.predicate == "observed_experience"
                    and existing.object == object_id and existing.source_text == source_payload
                    and existing.provenance == PROVENANCE
                    and existing.origin == f"live.infinita:{request.world_id}"
                    and existing.epoch == request.episode.logical_tick
                ):
                    raise HTTPException(status_code=409, detail="episode_id reused with different observed content")
                if key in pending:
                    receipt = evidence.save()
                    pending.discard(key)
                else:
                    receipt = evidence.receipt
                    if receipt is None:
                        receipt = evidence.save()
                stored = False
            else:
                edge = evidence.core.observe_relation(
                    subject, "observed_experience", object_id,
                    evidence_id=evidence_id,
                    source_text=source_payload,
                    provenance=PROVENANCE,
                    origin=f"live.infinita:{request.world_id}",
                    confidence=1.0,
                    namespace=namespace,
                    epoch=request.episode.logical_tick,
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
            "episode_id": request.episode.episode_id,
            "evidence_id": evidence_id,
            "episode_sha256": digest,
            "world_id": request.world_id,
            "persistence": receipt.as_dict(),
            "world_mutated": False,
            "selection_authority": False,
        }
