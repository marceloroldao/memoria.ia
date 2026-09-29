from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from memoria_resolutiva.external_episode_contract import (
    FORMAT, attach_external_episode_routes, canonical, ExternalEpisodeRequest,
)
from memoria_resolutiva.external_episode_incremental import (
    IncrementalExternalEpisodeStore, IncrementalEpisodeError, validated_payload,
)
from memoria_resolutiva.product_evidence import ProductEvidenceService

HEADERS = {"X-Memoria-Key": "local-test-secret"}


def episode(i: int, *, world: str = "nov-live-autonomous-001") -> dict:
    plan = f"plan_{i}"
    identity = {
        "system": "live.infinita", "world_id": world, "entity_id": "nov",
        "episode_id": "plan:" + plan,
    }
    unsigned = {
        "schema": FORMAT, "record_key": sha256(canonical(identity)).hexdigest(),
        "source": {
            **identity, "source_schema": "npc_episode_v1", "source_kind": "need_outcome",
            "plan_id": plan, "proposal_id": "pr_" + plan, "plan_revision": 0,
        },
        "observation": {
            "logical_tick": i, "need": "curiosity", "target_entity_id": "ancient_tree",
            "strategy_id": "explore",
            "context": {"period": "night", "weather": "clear", "region_id": "clearing", "danger_level": 0.35},
            "outcome": {"satisfaction": 0.3, "observed_risk": 0.35, "elapsed_ticks": 3,
                        "preemptions": 0, "replans": 0},
        },
        "authority": "observed-outcome-only", "world_write_authority": False,
    }
    return {**unsigned, "content_sha256": sha256(canonical(unsigned)).hexdigest()}


def request(i: int) -> ExternalEpisodeRequest:
    return ExternalEpisodeRequest.model_validate(episode(i))


def test_incremental_receipt_restart_core_and_idempotence(tmp_path):
    store = IncrementalExternalEpisodeStore(tmp_path)
    first = store.observe(request(1))
    assert first["ack"] and first["stored"]
    assert first["persistence"]["backend"] == "sqlite-incremental"
    assert first["persistence"]["sha256"] == first["content_sha256"]
    assert store.observe(request(1)) == {**first, "stored": False}
    assert store.count == 1
    rows = store.core.evidence_history(namespace="live:nov-live-autonomous-001")
    assert len(rows) == 1 and rows[0].provenance == "live.infinita:npc_episode_v1"
    assert rows[0].predicate == "observed_experience"
    store.close()
    reopened = IncrementalExternalEpisodeStore(tmp_path)
    assert reopened.count == 1
    assert reopened.observe(request(1))["stored"] is False
    assert len(reopened.core.evidence_history(namespace="live:nov-live-autonomous-001")) == 1
    reopened.close()


def test_immutable_conflict_and_integrity_rejection(tmp_path):
    store = IncrementalExternalEpisodeStore(tmp_path)
    store.observe(request(1))
    bad = episode(1)
    bad["observation"]["outcome"]["satisfaction"] = 0.9
    bad["content_sha256"] = sha256(canonical({k: v for k, v in bad.items() if k != "content_sha256"})).hexdigest()
    with pytest.raises(IncrementalEpisodeError, match="different observed content"):
        store.observe(ExternalEpisodeRequest.model_validate(bad))
    assert store.count == 1
    assert len(store.core.evidence_history(namespace="live:nov-live-autonomous-001")) == 1
    store.close()

    path = tmp_path / "external-episodes.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE observations SET content_sha256=? WHERE record_key=?", ("0"*64, episode(1)["record_key"]))
    with pytest.raises(IncrementalEpisodeError, match="corrupt incremental observation"):
        IncrementalExternalEpisodeStore(tmp_path)


def test_migration_of_real_legacy_snapshot_idempotent(tmp_path):
    legacy = ProductEvidenceService.open(tmp_path / "legacy", backend="sqlite", allow_fallback=False)
    from memoria_resolutiva.external_episode_contract import PROVENANCE
    for i in range(2):
        req = request(i)
        key, payload, digest, eid = validated_payload(req)
        source = req.source
        legacy.core.observe_relation(
            "live:episode:" + eid, "observed_experience",
            "live:entity:" + source.world_id + ":nov",
            evidence_id=eid, source_text=payload.decode("utf-8"), provenance=PROVENANCE,
            origin="live.infinita:" + source.world_id, confidence=1.0,
            namespace="live:" + source.world_id, epoch=i,
        )
        legacy.save()
    restored = ProductEvidenceService.open(tmp_path / "legacy", backend="sqlite", allow_fallback=False)
    store = IncrementalExternalEpisodeStore(tmp_path / "incremental")
    assert store.migrate_legacy(restored) == 2
    assert store.migrate_legacy(restored) == 0
    assert store.count == 2
    store.close()
    again = IncrementalExternalEpisodeStore(tmp_path / "incremental")
    assert again.count == 2
    assert again.observe(request(0))["stored"] is False
    assert again.observe(request(2))["stored"] is True
    again.close()
    assert restored.receipt_path.exists()  # old snapshots/receipt remain intact


def test_migration_rejects_unrelated_rows(tmp_path):
    legacy = ProductEvidenceService.open(tmp_path / "legacy", backend="sqlite", allow_fallback=False)
    legacy.core.observe_relation("a", "p", "b", evidence_id="other", source_text="x")
    legacy.save()
    store = IncrementalExternalEpisodeStore(tmp_path / "incremental")
    with pytest.raises(IncrementalEpisodeError, match="non-external"):
        store.migrate_legacy(legacy)
    assert store.count == 0
    store.close()


def test_real_authenticated_ingress_health_and_no_duplicate(tmp_path):
    evidence = ProductEvidenceService.open(tmp_path / "legacy", backend="sqlite", allow_fallback=False)
    store = IncrementalExternalEpisodeStore(tmp_path / "incremental")
    app = FastAPI()
    attach_external_episode_routes(app, api_key=HEADERS["X-Memoria-Key"], evidence=evidence, incremental=store)
    with TestClient(app) as client:
        route = "/api/v1/external/episodes"
        health = "/api/v1/external/episodes/health"
        assert client.post(route, json=episode(1)).status_code == 401
        assert client.get(health).status_code == 401
        assert client.get(health, headers=HEADERS).json()["mode"] == "sqlite-incremental"
        first = client.post(route, json=episode(1), headers=HEADERS)
        retry = client.post(route, json=episode(1), headers=HEADERS)
        assert first.status_code == 201 and first.json()["stored"] is True
        assert retry.status_code == 201 and retry.json()["stored"] is False
        bad = deepcopy(episode(1))
        bad["observation"]["outcome"]["satisfaction"] = 0.9
        bad["content_sha256"] = sha256(canonical({k: v for k, v in bad.items() if k != "content_sha256"})).hexdigest()
        assert client.post(route, json=bad, headers=HEADERS).status_code == 409
        assert client.get(health, headers=HEADERS).json()["observations"] == 1
        assert evidence.receipt is None
    store.close()


def test_disk_growth_100_1000_with_real_evidence_core(tmp_path):
    store = IncrementalExternalEpisodeStore(tmp_path)
    checkpoints = {}
    for i in range(1000):
        receipt = store.observe(request(i))
        assert receipt["ack"] is True
        if i + 1 in (100, 1000):
            checkpoints[i + 1] = sum(
                p.stat().st_size for p in tmp_path.iterdir() if p.is_file()
            )
    assert checkpoints[100] < 2 * 1024 * 1024
    assert checkpoints[1000] < 16 * 1024 * 1024
    assert checkpoints[1000] > checkpoints[100]
    store.close()
    restored = IncrementalExternalEpisodeStore(tmp_path)
    assert restored.count == 1000
    assert len(restored.core.evidence_history(namespace="live:nov-live-autonomous-001")) == 1000
    assert restored.observe(request(999))["stored"] is False
    restored.close()
