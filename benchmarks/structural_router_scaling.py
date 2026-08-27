from __future__ import annotations

import json
import random
import time

from memoria_resolutiva.structural_router_v96 import StructuralSemanticRouterV96

CONCEPTS = 1200
QUERIES = 3000


def build():
    router = StructuralSemanticRouterV96(relation_window=3, threshold=0.30, min_margin=0.04)
    t0 = time.perf_counter()
    for i in range(CONCEPTS):
        cid = f"c{i:04d}"
        router.register_pattern(cid, f"agent{i} action{i} object{i}")
        router.register_pattern(cid, f"agent{i} executes{i} object{i}")
        router.register_pattern(cid, f"agent{i} sends{i} object{i}")
    return router, time.perf_counter() - t0


def main():
    router, build_s = build()
    rng = random.Random(126)
    ids = [rng.randrange(CONCEPTS) for _ in range(QUERIES)]
    queries = [f"agent{i} action{i} object{i}" for i in ids]
    t0 = time.perf_counter()
    results = [router.resolve_text(q) for q in queries]
    query_s = time.perf_counter() - t0
    correct = sum(result.concept_id == f"c{i:04d}" for result, i in zip(results, ids))
    if correct != QUERIES:
        raise AssertionError((correct, QUERIES))
    print(json.dumps({
        "concepts": CONCEPTS,
        "patterns_per_concept": 3,
        "queries": QUERIES,
        "build_s": build_s,
        "query_s": query_s,
        "queries_per_s": QUERIES / query_s if query_s else None,
        "accuracy": correct / QUERIES,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
