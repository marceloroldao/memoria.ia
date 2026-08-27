from __future__ import annotations

import json
import random
import time

from memoria_resolutiva.structural_router_v96 import StructuralSemanticRouterV96, native_structural_available

CONCEPTS = 1200
QUERIES = 3000


def build(*, use_native: bool):
    router = StructuralSemanticRouterV96(relation_window=3, threshold=0.30, min_margin=0.04, use_native=use_native)
    t0 = time.perf_counter()
    for i in range(CONCEPTS):
        cid = f"c{i:04d}"
        router.register_pattern(cid, f"agent{i} action{i} object{i}")
        router.register_pattern(cid, f"agent{i} executes{i} object{i}")
        router.register_pattern(cid, f"agent{i} sends{i} object{i}")
    return router, time.perf_counter() - t0


def run(router, queries):
    t0 = time.perf_counter()
    results = [router.resolve_text(q) for q in queries]
    return time.perf_counter() - t0, results


def main():
    if not native_structural_available():
        raise SystemExit("native structural core unavailable")
    rng = random.Random(126)
    ids = [rng.randrange(CONCEPTS) for _ in range(QUERIES)]
    queries = [f"agent{i} action{i} object{i}" for i in ids]

    python_router, python_build = build(use_native=False)
    native_router, native_build = build(use_native=True)
    python_s, expected = run(python_router, queries)
    native_s, actual = run(native_router, queries)

    correct = 0
    for expected_result, actual_result, i in zip(expected, actual, ids):
        expected_id = f"c{i:04d}"
        if expected_result.concept_id != expected_id or actual_result.concept_id != expected_id:
            raise AssertionError((expected_result, actual_result, expected_id))
        if abs(expected_result.score - actual_result.score) > 1e-12 or abs(expected_result.margin - actual_result.margin) > 1e-12:
            raise AssertionError((expected_result, actual_result))
        correct += 1

    print(json.dumps({
        "concepts": CONCEPTS,
        "patterns_per_concept": 3,
        "queries": QUERIES,
        "python": {"build_s": python_build, "query_s": python_s},
        "native": {"build_s": native_build, "query_s": native_s},
        "speedup": {
            "build": python_build / native_build if native_build else None,
            "query": python_s / native_s if native_s else None,
        },
        "native_queries_per_s": QUERIES / native_s if native_s else None,
        "accuracy": correct / QUERIES,
        "parity": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
