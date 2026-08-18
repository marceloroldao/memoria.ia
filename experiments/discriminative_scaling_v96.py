from __future__ import annotations

from statistics import mean
from time import perf_counter

from memoria_resolutiva.discriminative_router_v96 import DiscriminativeSemanticRouterV96
from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96


def build(n: int):
    full = SemanticRouterV96(threshold=0.45, min_margin=0.05, indexed=False)
    disc = DiscriminativeSemanticRouterV96(
        threshold=0.45,
        min_margin=0.05,
        candidate_limit=32,
    )
    sentences = []
    for i in range(n):
        anchor = f"conceito{i}"
        synonym = f"termo{i}"
        domain = f"dominio{i % 25}"
        sentences.extend([
            f"o {anchor} opera no sistema comum {domain} assinatura{i} evento{i}",
            f"o {synonym} opera no sistema comum {domain} assinatura{i} evento{i}",
        ])
    full.observe(sentences)
    disc.observe(sentences)
    for i in range(n):
        cid = f"c{i}"
        full.register_concept(cid, [f"conceito{i}"])
        disc.register_concept(cid, [f"conceito{i}"])
    return full, disc


def timed(router, queries):
    start = perf_counter()
    results = [router.resolve_token(q) for q in queries]
    elapsed = perf_counter() - start
    return results, 1000.0 * elapsed / len(queries)


def main():
    for n in (100, 250, 500, 1000):
        full, disc = build(n)
        ids = list(range(min(n, 200)))
        queries = [f"termo{i}" for i in ids]

        full_results, full_ms = timed(full, queries)
        candidate_counts = []
        start = perf_counter()
        disc_results = []
        for q in queries:
            disc_results.append(disc.resolve_token(q))
            candidate_counts.append(disc.candidate_stats().candidate_concepts)
        disc_ms = 1000.0 * (perf_counter() - start) / len(queries)

        expected = [f"c{i}" for i in ids]
        full_correct = sum(r.concept_id == e for r, e in zip(full_results, expected))
        disc_correct = sum(r.concept_id == e for r, e in zip(disc_results, expected))
        parity = sum(a.concept_id == b.concept_id for a, b in zip(full_results, disc_results))

        print({
            "concepts": n,
            "queries": len(queries),
            "full_accuracy": full_correct / len(queries),
            "disc_accuracy": disc_correct / len(queries),
            "parity": parity / len(queries),
            "full_ms_per_query": full_ms,
            "disc_ms_per_query": disc_ms,
            "speedup": full_ms / disc_ms if disc_ms else float("inf"),
            "mean_candidates": mean(candidate_counts),
            "candidate_fraction": mean(candidate_counts) / n,
        })


if __name__ == "__main__":
    main()
