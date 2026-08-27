from __future__ import annotations

import json
import random
import time

from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96
from memoria_resolutiva.textual import native_context_available

CONCEPTS = 250
ANCHORS_PER_CONCEPT = 3
QUERIES = 1500


def build(use_native: bool):
    router = SemanticRouterV96(threshold=0.0, min_margin=0.0, use_native=use_native)
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
    return router


def run(router, queries):
    t0 = time.perf_counter()
    out = [router.resolve_token(q) for q in queries]
    return time.perf_counter() - t0, out


def main():
    if not native_context_available():
        raise SystemExit("native core unavailable")
    py = build(False)
    native = build(True)
    rng = random.Random(12345)
    queries = [f"query{rng.randrange(CONCEPTS)}" for _ in range(QUERIES)]
    py_s, py_out = run(py, queries)
    native_s, native_out = run(native, queries)
    for a, b in zip(py_out, native_out):
        assert a.concept_id == b.concept_id
        assert abs(a.score - b.score) <= 1e-12
        assert abs(a.margin - b.margin) <= 1e-12
    print(json.dumps({
        "concepts": CONCEPTS,
        "anchors_per_concept": ANCHORS_PER_CONCEPT,
        "queries": len(queries),
        "python_s": py_s,
        "native_s": native_s,
        "speedup": py_s / native_s if native_s else None,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
