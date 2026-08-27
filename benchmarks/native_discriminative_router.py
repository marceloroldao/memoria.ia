from __future__ import annotations

import json
import random
import time

from memoria_resolutiva.discriminative_router_v96 import DiscriminativeSemanticRouterV96
from memoria_resolutiva.textual import native_context_available

CONCEPTS = 1000
CANDIDATE_LIMIT = 32
QUERIES = 3000


def build(use_native: bool):
    t0 = time.perf_counter()
    router = DiscriminativeSemanticRouterV96(
        threshold=0.0,
        min_margin=0.0,
        candidate_limit=CANDIDATE_LIMIT,
        use_native=use_native,
    )
    sentences = []
    for i in range(CONCEPTS):
        anchor = f"a{i}"
        query = f"q{i}"
        family = f"family{i % 47}"
        domain = f"domain{i % 29}"
        rare = f"rare{i}"
        sentences.append(f"{query} {anchor} {rare} {family} {domain} shared context")
        sentences.append(f"{anchor} {query} {rare} {family} {domain} shared context")
    router.observe(sentences)
    for i in range(CONCEPTS):
        router.register_concept(f"c{i:04d}", [f"a{i}"])
    return router, time.perf_counter() - t0


def run(router, queries):
    t0 = time.perf_counter()
    results = []
    candidate_counts = []
    for query in queries:
        results.append(router.resolve_token(query))
        candidate_counts.append(router.candidate_stats().candidate_concepts)
    return time.perf_counter() - t0, results, candidate_counts


def assert_same(reference, candidate, ref_counts, candidate_counts):
    assert ref_counts == candidate_counts
    for a, b in zip(reference, candidate):
        assert a.concept_id == b.concept_id
        assert abs(a.score - b.score) <= 1e-12
        assert abs(a.margin - b.margin) <= 1e-12


def main():
    if not native_context_available():
        raise SystemExit("native core unavailable")
    py, py_build = build(False)
    native, native_build = build(True)
    rng = random.Random(24680)
    queries = [f"q{rng.randrange(CONCEPTS)}" for _ in range(QUERIES)]
    py_s, py_out, py_counts = run(py, queries)
    native_s, native_out, native_counts = run(native, queries)
    assert_same(py_out, native_out, py_counts, native_counts)
    print(json.dumps({
        "concepts": CONCEPTS,
        "candidate_limit": CANDIDATE_LIMIT,
        "queries": QUERIES,
        "python": {"build_s": py_build, "query_s": py_s},
        "native": {"build_s": native_build, "query_s": native_s},
        "mean_candidates": sum(native_counts) / len(native_counts),
        "speedup": {
            "build": py_build / native_build if native_build else None,
            "query": py_s / native_s if native_s else None,
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()
