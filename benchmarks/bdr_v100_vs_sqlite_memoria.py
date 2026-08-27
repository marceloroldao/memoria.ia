from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import struct
import subprocess
import tempfile
import time
from pathlib import Path

from memoria_resolutiva.layers import layer_bits
from memoria_resolutiva.node import digest_payload
from memoria_resolutiva.sqlite_store import SQLiteResolutiveMemory

BDR_VERSION = "v1.0.0"
BDR_REPOSITORY = "marceloroldao/resolutive-DB"


def deterministic_payload(index: int, size: int) -> bytes:
    seed = hashlib.blake2b(str(index).encode("ascii"), digest_size=32).digest()
    return bytes(seed[i % len(seed)] ^ ((i * 17 + index * 29) & 0xFF) for i in range(size))


def logical_records(memories: list[tuple[str, bytes]], max_layer: int = 3):
    records: dict[str, bytes] = {}
    for memory_id, data in memories:
        records[f"m:{memory_id}"] = data
        for layer in range(max_layer + 1):
            width = layer_bits(layer) // 8
            for local_time, offset in enumerate(range(0, len(data), width)):
                payload = data[offset : offset + width]
                if not payload:
                    continue
                node_id = digest_payload(payload, layer)
                records.setdefault(f"n:{node_id}", layer.to_bytes(2, "big") + payload)
                records[f"o:{memory_id}:{layer}:{local_time}"] = node_id.encode("ascii")
    return sorted(records.items())


def write_workload(path: Path, records: list[tuple[str, bytes]]) -> None:
    with path.open("wb") as fh:
        fh.write(struct.pack(">Q", len(records)))
        for key, value in records:
            key_bytes = key.encode("utf-8")
            fh.write(struct.pack(">II", len(key_bytes), len(value)))
            fh.write(key_bytes)
            fh.write(value)


def directory_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) if root.exists() else 0


def bench_sqlite_logical(root: Path, records: list[tuple[str, bytes]]) -> dict:
    path = root / "logical.sqlite3"
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE kv(key TEXT PRIMARY KEY, value BLOB NOT NULL)")

    started = time.perf_counter()
    with db:
        db.executemany("INSERT INTO kv(key,value) VALUES(?,?)", records)
    write_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    for key, expected in records:
        row = db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        if row is None or bytes(row[0]) != expected:
            raise RuntimeError(f"SQLite logical read mismatch for {key}")
    read_ms = (time.perf_counter() - started) * 1000
    db.close()

    started = time.perf_counter()
    reopened = sqlite3.connect(path)
    for key, expected in records:
        row = reopened.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        if row is None or bytes(row[0]) != expected:
            raise RuntimeError(f"SQLite logical reopen mismatch for {key}")
    reopen_ms = (time.perf_counter() - started) * 1000
    reopened.close()

    return {
        "engine": "sqlite-logical-kv",
        "records": len(records),
        "write_ms": write_ms,
        "read_ms": read_ms,
        "reopen_verify_ms": reopen_ms,
        "verified": len(records),
        "reopen_verified": len(records),
        "disk_bytes": directory_bytes(root),
    }


def bench_memoria_sqlite(root: Path, memories: list[tuple[str, bytes]], max_layer: int) -> dict:
    path = root / "memoria.sqlite3"
    store = SQLiteResolutiveMemory(path, max_layer=max_layer)
    started = time.perf_counter()
    for memory_id, payload in memories:
        store.add(memory_id, payload)
    write_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    for memory_id, expected in memories:
        if store.reconstruct(memory_id) != expected:
            raise RuntimeError(f"Memoria SQLite reconstruct mismatch for {memory_id}")
    read_ms = (time.perf_counter() - started) * 1000
    stats = store.stats()
    store.close()

    started = time.perf_counter()
    reopened = SQLiteResolutiveMemory(path, max_layer=max_layer)
    for memory_id, expected in memories:
        if reopened.reconstruct(memory_id) != expected:
            raise RuntimeError(f"Memoria SQLite reopen mismatch for {memory_id}")
    reopen_ms = (time.perf_counter() - started) * 1000
    reopened.close()

    return {
        "engine": "memoria-sqlite-current",
        "memories": len(memories),
        "write_ms": write_ms,
        "read_ms": read_ms,
        "reopen_verify_ms": reopen_ms,
        "disk_bytes": directory_bytes(root),
        "stats": stats,
    }


def bench_bdr(driver: Path, root: Path, workload: Path) -> dict:
    proc = subprocess.run(
        [str(driver), str(root), str(workload)],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(proc.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Memoria.ia persistence comparison: SQLite vs frozen BDR v1.0.0")
    parser.add_argument("--bdr-driver", type=Path, required=True)
    parser.add_argument("--memories", type=int, default=256)
    parser.add_argument("--payload-bytes", type=int, default=256)
    parser.add_argument("--max-layer", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.memories < 1 or args.payload_bytes < 1 or args.max_layer < 0:
        raise SystemExit("memories/payload-bytes must be positive and max-layer >= 0")

    memories = [(f"memory-{i:06d}", deterministic_payload(i, args.payload_bytes)) for i in range(args.memories)]
    materialize_start = time.perf_counter()
    records = logical_records(memories, max_layer=args.max_layer)
    materialize_ms = (time.perf_counter() - materialize_start) * 1000

    with tempfile.TemporaryDirectory(prefix="memoria-bdr-v100-") as tmp:
        root = Path(tmp)
        workload = root / "workload.bin"
        write_workload(workload, records)

        sqlite_logical = bench_sqlite_logical(root / "sqlite-logical", records)
        memoria_sqlite = bench_memoria_sqlite(root / "memoria-current", memories, args.max_layer)
        bdr = bench_bdr(args.bdr_driver, root / "bdr-v100", workload)

        if bdr.get("records") != len(records) or bdr.get("verified") != len(records) or bdr.get("reopen_verified") != len(records):
            raise RuntimeError("BDR v1.0.0 did not verify the complete logical workload")

        result = {
            "schema": "memoria-bdr-comparison-v1",
            "bdr": {"repository": BDR_REPOSITORY, "version": BDR_VERSION},
            "workload": {
                "memories": args.memories,
                "payload_bytes": args.payload_bytes,
                "max_layer": args.max_layer,
                "logical_records": len(records),
                "logical_payload_bytes": sum(len(v) for _, v in records),
                "materialize_ms": materialize_ms,
            },
            "current_memoria_sqlite": memoria_sqlite,
            "storage_only": {
                "sqlite": sqlite_logical,
                "bdr_v1_0_0": bdr,
            },
        }

    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
