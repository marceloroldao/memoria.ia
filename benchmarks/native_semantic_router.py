from __future__ import annotations

import json
import random
import time

from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96
from memoria_resolutiva.textual import native_context_available

CONCEPTS = 250
ANCHORS_PER_CONCEPT = 3
QUERIES = 1500


def build(use_native: bool, *, native_authoritative: bool = False):
    t0 = time.perf_counter()
    router = SemanticRouterV96(
        threshold=0.0,
        min_margin=0.0,
        use_native=use_native,
        native_authoritative=native_authoritative,
    )
    sentences = []
    mapping = {}
    for cid in range(CONCEPTS):
        anchors = [f"a{cid}_{j}" for j in range(ANCHORS_PER_CONCEPT)]
        mapping[f"c{cid:04d}"] = anchors
        for anchor in anchors:
            sentences.append(f"query{cid} {anchor} family{cid % 31} domain{cid % 17} shared context")
            sentences.append(f"{anchor} query{cid} shared context family{cid % 31} domain{cid % 17}")
    router.observe(sentences)
    for concept_id, anchors in mapping.items():
        router.register_concept(concept_id, anchors)
    return router, time.perf_counter() - t0


def run(router, queries):
    t0 = time.perf_counter()
    out = [router.resolve_token(q) for q in queries]
    return time.perf_counter() - t0, out


def assert_same(reference, candidate):
    for a, b in zip(reference, candidate):
        assert a.concept_id == b.concept_id
        assert abs(a.score - b.score) <= 1e-12
        assert abs(a.margin - b.margin) <= 1e-12


def main():
    if not native_context_available():
        raise SystemExit("native core unavailable")
    py, py_build = build(False)
    mirrored, mirrored_build = build(True)
    authoritative, authoritative_build = build(True, native_authoritative=True)
    rng = random.Random(12345)
    queries = [f"query{rng.randrange(CONCEPTS)}" for _ in range(QUERIES)]
    py_s, py_out = run(py, queries)
    mirrored_s, mirrored_out = run(mirrored, queries)
    authoritative_s, authoritative_out = run(authoritative, queries)
    assert_same(py_out, mirrored_out)
    assert_same(py_out, authoritative_out)
    print(json.dumps({
        "concepts": CONCEPTS,
        "anchors_per_concept": ANCHORS_PER_CONCEPT,
        "queries": len(queries),
        "python": {"build_s": py_build, "query_s": py_s},
        "native_mirrored": {"build_s": mirrored_build, "query_s": mirrored_s},
        "native_authoritative": {"build_s": authoritative_build, "query_s": authoritative_s},
        "speedup": {
            "mirrored_query_vs_python": py_s / mirrored_s if mirrored_s else None,
            "authoritative_query_vs_python": py_s / authoritative_s if authoritative_s else None,
            "authoritative_build_vs_mirrored": mirrored_build / authoritative_build if authoritative_build else None,
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()
