#!/usr/bin/env python3
"""Reproducible side-by-side SQL incremental vs native BDR candidate.

Scratch-only; never consumes or writes the real Nov ledger, local production
database, systemd units, credentials, or world. Real V2 EvidenceCore is used by
both backends. BDR must be an explicitly supplied pinned native C ABI library.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import resource
import tempfile
from time import perf_counter

from memoria_resolutiva.external_episode_contract import ExternalEpisodeRequest, FORMAT, canonical
from memoria_resolutiva.external_episode_incremental import IncrementalExternalEpisodeStore
from memoria_resolutiva.external_episode_bdr_candidate import BdrExternalEpisodeCandidate


def episode(i: int) -> ExternalEpisodeRequest:
    plan = f"benchmark_{i}"
    identity = {
        "system": "live.infinita", "world_id": "benchmark-not-production",
        "entity_id": "nov", "episode_id": "plan:" + plan,
    }
    unsigned = {
        "schema": FORMAT, "record_key": sha256(canonical(identity)).hexdigest(),
        "source": {
            **identity, "source_schema": "npc_episode_v1", "source_kind": "need_outcome",
            "plan_id": plan, "proposal_id": f"proposal_{i}", "plan_revision": 0,
        },
        "observation": {
            "logical_tick": i, "need": "curiosity", "target_entity_id": "ancient_tree",
            "strategy_id": "explore", "context": {
                "period": "night", "weather": "clear", "region_id": "clearing", "danger_level": .35,
            },
            "outcome": {
                "satisfaction": .3, "observed_risk": .35,
                "elapsed_ticks": 3, "preemptions": 0, "replans": 0,
            },
        },
        "authority": "observed-outcome-only", "world_write_authority": False,
    }
    return ExternalEpisodeRequest.model_validate({
        **unsigned, "content_sha256": sha256(canonical(unsigned)).hexdigest(),
    })


def size(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def shape(core) -> tuple:
    return tuple(
        (x.subject, x.predicate, x.object, x.evidence_id, x.source_text,
         x.namespace, x.epoch, x.provenance, x.origin, x.confidence)
        for x in core.evidence_history(namespace="live:benchmark-not-production")
    )


def run(scale: int, native: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="memoria-bdr-parity-scratch-") as directory:
        root = Path(directory)
        sqlite_dir, bdr_dir = root / "sqlite", root / "bdr"
        sqlite = IncrementalExternalEpisodeStore(sqlite_dir)
        bdr = BdrExternalEpisodeCandidate(bdr_dir, library_path=native)
        timings = {"sqlite": 0.0, "bdr": 0.0}
        last_sqlite = last_bdr = None
        for i in range(scale):
            row = episode(i)
            t = perf_counter()
            last_sqlite = sqlite.observe(row)
            timings["sqlite"] += perf_counter() - t
            t = perf_counter()
            last_bdr = bdr.observe(row)
            timings["bdr"] += perf_counter() - t
            assert last_sqlite["record_key"] == last_bdr["record_key"]
            assert last_sqlite["content_sha256"] == last_bdr["content_sha256"]
            assert last_sqlite["ack"] and last_bdr["ack"]
            assert last_sqlite["stored"] and last_bdr["stored"]
        assert sqlite.count == bdr.count == scale
        assert shape(sqlite.core) == shape(bdr.core)
        live_sizes = {"sqlite": size(sqlite_dir), "bdr": size(bdr_dir)}
        sqlite.close()
        bdr.close()
        cold_start = perf_counter()
        sql_restored = IncrementalExternalEpisodeStore(sqlite_dir)
        sqlite_reopen_s = perf_counter() - cold_start
        cold_start = perf_counter()
        bdr_restored = BdrExternalEpisodeCandidate(bdr_dir, library_path=native)
        bdr_reopen_s = perf_counter() - cold_start
        assert shape(sql_restored.core) == shape(bdr_restored.core)
        assert sql_restored.count == bdr_restored.count == scale
        again_sqlite = sql_restored.observe(episode(scale - 1))
        again_bdr = bdr_restored.observe(episode(scale - 1))
        assert again_sqlite["stored"] is False and again_bdr["stored"] is False
        assert bdr_restored._db.last_sequence() == bdr_restored._db.durable_sequence()
        result = {
            "schema": "memoria-v2-external-backend-parity/1",
            "episodes": scale,
            "sqlite_live_bytes": live_sizes["sqlite"],
            "bdr_live_bytes": live_sizes["bdr"],
            "sqlite_after_close_bytes": size(sqlite_dir),
            "bdr_after_close_bytes": size(bdr_dir),
            "sqlite_ingest_seconds": round(timings["sqlite"], 4),
            "bdr_ingest_seconds": round(timings["bdr"], 4),
            "sqlite_cold_reopen_seconds": round(sqlite_reopen_s, 4),
            "bdr_cold_reopen_seconds": round(bdr_reopen_s, 4),
            "max_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "graph_parity": True,
            "identity_digest_parity": True,
            "duplicate_idempotence": True,
            "bdr_durable_sequence": bdr_restored._db.durable_sequence(),
            "production_modified": False,
        }
        sql_restored.close()
        bdr_restored.close()
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bdr-library", required=True, type=Path)
    parser.add_argument("--scale", type=int, choices=(100, 1000, 10000), default=100)
    args = parser.parse_args()
    if not args.bdr_library.is_file():
        parser.error("exact native BDR shared library not found")
    print(json.dumps(run(args.scale, str(args.bdr_library.resolve())), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
