from __future__ import annotations

import json
import random
import time
from collections import Counter

from memoria_resolutiva.semantic_router_v96 import AdaptiveSemanticRouterV96, SemanticRouterV96
from memoria_resolutiva.textual import native_context_available

CONCEPTS = 5000
CLEAR_QUERIES = 950
AMBIGUOUS_QUERIES = 50


def build_corpus(n: int):
    sentences = []
    anchors = {}
    for i in range(n):
        cid = f"c{i:05d}"
        anchor = f"anchor{i}"
        anchors[cid] = (anchor,)
        family = f"family{i % 251}"
        domain = f"domain{i % 97}"
        sentences.extend([
            f"query{i} {anchor} rare{i} {family} {domain} shared system context",
            f"{anchor} query{i} rare{i} {family} {domain} shared system context",
        ])
    return sentences, anchors


def build(router_cls, sentences, anchors):
    router = router_cls(threshold=0.0, min_margin=0.0, use_native=True)
    router.observe(sentences)
    for cid, values in anchors.items():
        router.register_concept(cid, values)
    return router


def run_full(router, queries):
    t0 = time.perf_counter()
    out = [router.resolve_token(q) for q in queries]
    return time.perf_counter() - t0, out


def run_adaptive(router, queries):
    modes = Counter()
    out = []
    t0 = time.perf_counter()
    for q in queries:
        out.append(router.resolve_token(q))
        modes[router.last_route_mode] += 1
    return time.perf_counter() - t0, out, modes


def main():
    if not native_context_available():
        raise SystemExit("native core unavailable")
    sentences, anchors = build_corpus(CONCEPTS)
    full = build(SemanticRouterV96, sentences, anchors)
    adaptive = AdaptiveSemanticRouterV96(
        threshold=0.0,
        min_margin=0.0,
        use_native=True,
        adaptive_threshold=512,
        candidate_limit=32,
    )
    adaptive.observe(sentences)
    for cid, values in anchors.items():
        adaptive.register_concept(cid, values)

    rng = random.Random(126)
    queries = [f"query{rng.randrange(CONCEPTS)}" for _ in range(CLEAR_QUERIES)]
    queries.extend(["shared", "system", "context", "family1", "domain1"] * (AMBIGUOUS_QUERIES // 5))
    rng.shuffle(queries)

    full_s, expected = run_full(full, queries)
    adaptive_s, actual, modes = run_adaptive(adaptive, queries)
    for a, b in zip(expected, actual):
        if a.concept_id != b.concept_id or abs(a.score-b.score) > 1e-12 or abs(a.margin-b.margin) > 1e-12:
            raise AssertionError((a, b))

    print(json.dumps({
        "concepts": CONCEPTS,
        "queries": len(queries),
        "clear_queries": CLEAR_QUERIES,
        "ambiguous_queries": AMBIGUOUS_QUERIES,
        "candidate_limit": 32,
        "full_query_s": full_s,
        "adaptive_query_s": adaptive_s,
        "effective_speedup": full_s / adaptive_s if adaptive_s else None,
        "route_modes": dict(sorted(modes.items())),
        "full_verify_fraction": modes.get("full_verify", 0) / len(queries),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
