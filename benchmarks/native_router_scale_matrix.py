from __future__ import annotations

import json
import random
import time

from memoria_resolutiva.discriminative_router_v96 import DiscriminativeSemanticRouterV96
from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96
from memoria_resolutiva.textual import native_context_available

CONCEPT_SIZES = (1000, 5000, 10000)
LIMITS = (8, 16, 32, 64)
QUERIES = 1000


def build_corpus(n: int):
    sentences = []
    anchors = {}
    for i in range(n):
        a0 = f"anchor{i}_0"
        a1 = f"anchor{i}_1"
        a2 = f"anchor{i}_2"
        anchors[f"c{i:05d}"] = (a0, a1, a2)
        rare = f"rare{i}"
        family = f"family{i % 251}"
        domain = f"domain{i % 97}"
        sentences.append(f"query{i} {a0} {rare} {family} {domain} shared context")
        sentences.append(f"{a1} query{i} {rare} {family} {domain} shared context")
        sentences.append(f"{a2} query{i} {rare} {family} {domain} shared context")
    return sentences, anchors


def build_full(sentences, anchors):
    t0 = time.perf_counter()
    router = SemanticRouterV96(threshold=0.0, min_margin=0.0, use_native=True)
    router.observe(sentences)
    for cid, values in anchors.items():
        router.register_concept(cid, values)
    return router, time.perf_counter() - t0


def build_disc(sentences, anchors, limit):
    t0 = time.perf_counter()
    router = DiscriminativeSemanticRouterV96(threshold=0.0, min_margin=0.0, candidate_limit=limit)
    router.observe(sentences)
    for cid, values in anchors.items():
        router.register_concept(cid, values)
    return router, time.perf_counter() - t0


def run(router, queries):
    out = []
    t0 = time.perf_counter()
    for q in queries:
        out.append(router.resolve_token(q))
    return time.perf_counter() - t0, out


def main():
    if not native_context_available():
        raise SystemExit("native core unavailable")
    rng = random.Random(126)
    rows = []
    for n in CONCEPT_SIZES:
        sentences, anchors = build_corpus(n)
        queries = [f"query{rng.randrange(n)}" for _ in range(QUERIES)]
        full, full_build = build_full(sentences, anchors)
        full_s, full_out = run(full, queries)
        for limit in LIMITS:
            disc, disc_build = build_disc(sentences, anchors, limit)
            disc_s, disc_out = run(disc, queries)
            same = sum(1 for a, b in zip(full_out, disc_out) if a.concept_id == b.concept_id)
            mean_candidates = 0.0
            if queries:
                total = 0
                for q in queries[:200]:
                    disc.resolve_token(q)
                    total += disc.candidate_stats().candidate_concepts
                mean_candidates = total / min(200, len(queries))
            rows.append({
                "concepts": n,
                "candidate_limit": limit,
                "queries": len(queries),
                "full_build_s": full_build,
                "disc_build_s": disc_build,
                "full_query_s": full_s,
                "disc_query_s": disc_s,
                "speedup_vs_full": full_s / disc_s if disc_s else None,
                "recall_vs_full": same / len(queries),
                "mean_candidates": mean_candidates,
                "retained_fraction": mean_candidates / n,
            })
    print(json.dumps({"matrix": rows}, sort_keys=True))


if __name__ == "__main__":
    main()
