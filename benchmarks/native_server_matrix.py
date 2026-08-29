from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import platform
import resource
import shutil
import sys
import time
from typing import Iterable

from memoria_resolutiva.native_conversation import NativeConversationService


def percentile(values: Iterable[float], percent: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    rank = max(0, min(len(ordered) - 1, math.ceil((percent / 100.0) * len(ordered)) - 1))
    return ordered[rank]


def sample_indexes(size: int, limit: int) -> list[int]:
    count = min(size, limit)
    if count <= 1:
        return [0]
    return sorted({round(i * (size - 1) / (count - 1)) for i in range(count)})


def rss_kib() -> tuple[int, int]:
    current = 0
    try:
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                current = int(line.split()[1])
                break
    except OSError:
        pass

    usage = resource.getrusage(resource.RUSAGE_SELF)
    peak = int(usage.ru_maxrss)
    if sys.platform == "darwin":
        peak //= 1024
    return current, peak


def directory_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return total
    for path in root.rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total


def elapsed_ms(start_ns: int) -> float:
    return (time.perf_counter_ns() - start_ns) / 1_000_000.0


def record_text(index: int) -> str:
    return f"item{index:06d} is value{index:06d}"


def record_query(index: int) -> str:
    return f"item{index:06d}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Memoria.ia native production-path benchmark matrix")
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--size", required=True, type=int, choices=(100, 1000, 10000))
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--resolve-samples", type=int, default=200)
    args = parser.parse_args()

    if not args.library.is_file():
        raise SystemExit(f"native library not found: {args.library}")
    if args.resolve_samples < 1:
        raise SystemExit("--resolve-samples must be >= 1")

    shutil.rmtree(args.data_dir, ignore_errors=True)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    organization_id = f"benchmark-native-{args.size}"
    session_id = "benchmark-session"
    ingest_ms: list[float] = []
    resolve_ms: list[float] = []
    context_bytes: list[float] = []

    service = NativeConversationService(
        library_path=args.library,
        data_dir=args.data_dir,
        organization_id=organization_id,
    )

    for index in range(args.size):
        start = time.perf_counter_ns()
        result = service.ingest(
            role="user",
            text=record_text(index),
            session_id=session_id,
            order=index,
        )
        ingest_ms.append(elapsed_ms(start))
        if result.unresolved or len(result.relations) != 1:
            raise RuntimeError(f"unexpected ingest result at index {index}: {result}")

    current_after_ingest_kib, peak_after_ingest_kib = rss_kib()

    indexes = sample_indexes(args.size, args.resolve_samples)
    for index in indexes:
        start = time.perf_counter_ns()
        result = service.resolve(query=record_query(index), session_id=session_id)
        resolve_ms.append(elapsed_ms(start))
        if result.status != "HIT":
            raise RuntimeError(f"resolve did not HIT at index {index}: {result.status}")
        expected = record_text(index)
        if expected not in result.selected_context:
            raise RuntimeError(
                f"resolve selected unexpected context at index {index}: {result.selected_context!r}"
            )
        context_bytes.append(float(len(result.selected_context.encode("utf-8"))))

    current_after_resolve_kib, peak_after_resolve_kib = rss_kib()
    store_bytes_before_restart = directory_bytes(args.data_dir)

    service.close()

    restart_start = time.perf_counter_ns()
    reopened = NativeConversationService(
        library_path=args.library,
        data_dir=args.data_dir,
        organization_id=organization_id,
    )
    restart_load_ms = elapsed_ms(restart_start)

    verify_index = indexes[len(indexes) // 2]
    first_resolve_start = time.perf_counter_ns()
    restarted_result = reopened.resolve(query=record_query(verify_index), session_id=session_id)
    first_resolve_after_restart_ms = elapsed_ms(first_resolve_start)
    if restarted_result.status != "HIT" or record_text(verify_index) not in restarted_result.selected_context:
        raise RuntimeError("restart verification failed")

    current_after_restart_kib, peak_after_restart_kib = rss_kib()
    store_bytes_after_restart = directory_bytes(args.data_dir)
    reopened.close()

    payload = {
        "schema": "memoria.native-benchmark.v1",
        "size": args.size,
        "resolve_samples": len(indexes),
        "library": str(args.library),
        "git_sha": os.getenv("GITHUB_SHA"),
        "runner": os.getenv("RUNNER_NAME"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "metrics": {
            "ingest_ms": {
                "p50": round(percentile(ingest_ms, 50), 6),
                "p95": round(percentile(ingest_ms, 95), 6),
                "count": len(ingest_ms),
            },
            "resolve_ms": {
                "p50": round(percentile(resolve_ms, 50), 6),
                "p95": round(percentile(resolve_ms, 95), 6),
                "count": len(resolve_ms),
            },
            "selected_context_bytes": {
                "p50": int(percentile(context_bytes, 50)),
                "p95": int(percentile(context_bytes, 95)),
            },
            "rss_mib": {
                "after_ingest": round(current_after_ingest_kib / 1024.0, 3),
                "after_resolve": round(current_after_resolve_kib / 1024.0, 3),
                "after_restart": round(current_after_restart_kib / 1024.0, 3),
                "peak": round(max(peak_after_ingest_kib, peak_after_resolve_kib, peak_after_restart_kib) / 1024.0, 3),
            },
            "restart_load_ms": round(restart_load_ms, 6),
            "first_resolve_after_restart_ms": round(first_resolve_after_restart_ms, 6),
            "store_bytes": store_bytes_after_restart,
            "store_bytes_before_restart": store_bytes_before_restart,
        },
        "validation": {
            "all_ingests_created_one_relation": True,
            "all_sampled_resolves_hit_expected_context": True,
            "restart_resolve_hit_expected_context": True,
            "store_size_stable_across_restart": store_bytes_after_restart == store_bytes_before_restart,
        },
    }

    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    compact = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    print(f"BENCHMARK_RESULT={compact}")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
