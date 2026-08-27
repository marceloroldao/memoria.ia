from __future__ import annotations

import json
import random
import time

from memoria_resolutiva.hybrid_text_router_v96 import HybridTextRouterV96

CONCEPTS = 600
QUERIES = 2400
STRUCTURAL_FRACTION = 0.25
OPEN_FRACTION = 0.05


def build():
    router = HybridTextRouterV96(
        semantic_threshold=0.0,
        semantic_min_margin=0.02,
        structural_threshold=0.45,
        structural_min_margin=0.08,
        use_native=True,
    )
    corpus = []
    for i in range(CONCEPTS):
        corpus.extend([
            f"topic{i} anchor{i} context{i % 53} shared",
            f"anchor{i} topic{i} context{i % 53} shared",
        ])
    # Add symmetric role corpus for structural-only pairs.
    structural_ids = int(CONCEPTS * STRUCTURAL_FRACTION)
    for i in range(structural_ids):
        corpus.extend([
            f"agent{i} action{i} object{i}",
            f"object{i} action{i} agent{i}",
        ])
    router.observe(corpus)

    for i in range(CONCEPTS):
        router.register_semantic_concept(f"semantic{i}", {f"anchor{i}"})
    for i in range(structural_ids):
        # Identical semantic anchors create deliberate semantic ambiguity.
        router.register_semantic_concept(f"forward{i}", {f"agent{i}", f"object{i}"})
        router.register_semantic_concept(f"reverse{i}", {f"agent{i}", f"object{i}"})
        router.register_structural_pattern(f"forward{i}", f"agent{i} action{i} object{i}")
        router.register_structural_pattern(f"reverse{i}", f"object{i} action{i} agent{i}")
    return router, structural_ids


def main():
    router, structural_ids = build()
    rng = random.Random(126)
    structural_n = int(QUERIES * STRUCTURAL_FRACTION)
    open_n = int(QUERIES * OPEN_FRACTION)
    semantic_n = QUERIES - structural_n - open_n

    queries = []
    for _ in range(semantic_n):
        i = rng.randrange(CONCEPTS)
        queries.append((f"topic{i} anchor{i}", f"semantic{i}"))
    for _ in range(structural_n):
        i = rng.randrange(structural_ids)
        if rng.randrange(2):
            queries.append((f"agent{i} action{i} object{i}", f"forward{i}"))
        else:
            queries.append((f"object{i} action{i} agent{i}", f"reverse{i}"))
    for i in range(open_n):
        queries.append((f"unknown{i} novel{i} token{i}", None))
    rng.shuffle(queries)

    t0 = time.perf_counter()
    results = [router.resolve_text(text) for text, _ in queries]
    query_s = time.perf_counter() - t0

    correct = sum(result.concept_id == expected for result, (_, expected) in zip(results, queries))
    if correct != QUERIES:
        failures = [(q, e, r.concept_id, r.source) for r, (q, e) in zip(results, queries) if r.concept_id != e][:10]
        raise AssertionError(failures)

    stats = router.stats()
    print(json.dumps({
        "concepts": CONCEPTS,
        "queries": QUERIES,
        "semantic_queries": semantic_n,
        "structural_queries": structural_n,
        "open_queries": open_n,
        "query_s": query_s,
        "queries_per_s": QUERIES / query_s if query_s else None,
        "accuracy": correct / QUERIES,
        "routes": {
            "semantic": stats.semantic,
            "structural": stats.structural,
            "consensus": stats.consensus,
            "conflict": stats.conflict,
            "unresolved": stats.unresolved,
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()
