from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from memoria_resolutiva.bdr_store import BDRPolicy, BDRResolutiveMemory
from memoria_resolutiva.sqlite_store import SQLiteResolutiveMemory


def payload_for(index: int, size: int) -> bytes:
    x = 0x9E3779B97F4A7C15 ^ (index * 0xD1B54A32D192ED03)
    out = bytearray(size)
    for i in range(size):
        x ^= x >> 12
        x ^= (x << 25) & ((1 << 64) - 1)
        x ^= x >> 27
        x = (x * 2685821657736338717) & ((1 << 64) - 1)
        out[i] = (x >> 56) & 0xFF
    return bytes(out)


def run_store(store, payloads):
    start = time.perf_counter()
    for i, payload in enumerate(payloads):
        store.add(f"memory-{i:08d}", payload)
    write_s = time.perf_counter() - start

    start = time.perf_counter()
    for i, payload in enumerate(payloads):
        got = store.reconstruct(f"memory-{i:08d}")
        if got != payload:
            raise RuntimeError(f"reconstruct mismatch at {i}")
    read_s = time.perf_counter() - start
    stats = store.stats()
    return write_s, read_s, stats


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--memories", type=int, default=256)
    p.add_argument("--payload-bytes", type=int, default=512)
    p.add_argument("--sync-every", type=int, default=1)
    args = p.parse_args()

    payloads = [payload_for(i, args.payload_bytes) for i in range(args.memories)]
    with tempfile.TemporaryDirectory(prefix="memoria-bdr-e2e-") as td:
        root = Path(td)

        sqlite = SQLiteResolutiveMemory(root / "sqlite.db", max_layer=3)
        sw, sr, ss = run_store(sqlite, payloads)
        sqlite.close()

        bdr = BDRResolutiveMemory(
            root / "bdr",
            max_layer=3,
            policy=BDRPolicy(sync_every_memories=args.sync_every),
        )
        bw, br, bs = run_store(bdr, payloads)
        bdr.flush()
        bdr.close()

        if bs != ss:
            raise RuntimeError(f"stats mismatch: sqlite={ss} bdr={bs}")

        result = {
            "memories": args.memories,
            "payload_bytes": args.payload_bytes,
            "sync_every": args.sync_every,
            "sqlite": {"write_s": sw, "read_s": sr, "stats": ss},
            "bdr": {"write_s": bw, "read_s": br, "stats": bs},
            "speedup": {
                "write": sw / bw if bw else None,
                "read": sr / br if br else None,
            },
        }
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
