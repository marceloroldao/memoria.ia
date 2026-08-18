from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from time import perf_counter

from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96


@dataclass(frozen=True)
class Case:
    query: str
    expected: str | None


def build_router(n_concepts: int, *, threshold: float = 0.60, min_margin: float = 0.08):
    r = SemanticRouterV96(threshold=threshold, min_margin=min_margin)
    sentences = []
    for i in range(n_concepts):
        anchor = f"conceito{i}"
        alias = f"alias{i}"
        domain = f"dominio{i}"
        context = f"contexto{i}"
        sentences.extend([
            f"o {anchor} aparece no {domain} com {context}",
            f"o {alias} aparece no {domain} com {context}",
            f"o {anchor} permanece associado a {domain} e {context}",
            f"o {alias} permanece associado a {domain} e {context}",
        ])
        r.register_concept(f"c{i}", [anchor])
    r.observe(sentences)
    return r


def evaluate(n_concepts: int, repeats: int = 20):
    router = build_router(n_concepts, threshold=0.45, min_margin=0.05)
    cases = [Case(f"alias{i}", f"c{i}") for i in range(n_concepts)]
    cases += [Case(f"desconhecido{i}", None) for i in range(max(1, n_concepts // 4))]

    correct = 0
    false_positive = 0
    abstained = 0
    latencies_us = []

    for _ in range(repeats):
        for case in cases:
            t0 = perf_counter()
            result = router.resolve_token(case.query)
            latencies_us.append((perf_counter() - t0) * 1e6)

            if result.concept_id == case.expected:
                correct += 1
            elif case.expected is None and result.concept_id is not None:
                false_positive += 1
            elif case.expected is not None and result.concept_id is None:
                abstained += 1

    total = len(cases) * repeats
    resolved_known = n_concepts * repeats - abstained
    known_total = n_concepts * repeats
    return {
        "concepts": n_concepts,
        "queries": total,
        "accuracy": correct / total,
        "known_deflection_rate": resolved_known / known_total if known_total else 0.0,
        "false_positive_rate": false_positive / (max(1, n_concepts // 4) * repeats),
        "abstention_rate_known": abstained / known_total if known_total else 0.0,
        "mean_latency_us": mean(latencies_us),
        "max_latency_us": max(latencies_us),
    }


def main():
    for n in (10, 25, 50, 100, 250):
        print(evaluate(n))


if __name__ == "__main__":
    main()
