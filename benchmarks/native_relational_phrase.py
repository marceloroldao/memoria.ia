from __future__ import annotations

import json
import random
import time

from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96
from memoria_resolutiva.textual import native_context_available

CONCEPTS = 512
QUERIES = 1200


def build_router():
    router = SemanticRouterV96(radius=3, threshold=0.0, min_margin=0.0, use_native=True)
    sentences = []
    for i in range(CONCEPTS):
        a = f"anchor{i}"
        rel = f"rel{i}"
        obj = f"object{i}"
        family = f"family{i % 31}"
        sentences.extend([f"{a} {rel} {obj} {family}"] * 4)
    router.observe(sentences)
    for i in range(CONCEPTS):
        router.register_concept(f"c{i}", {f"anchor{i}", f"object{i}"})
    return router


def main():
    if not native_context_available():
        raise SystemExit("native core unavailable")
    router = build_router()
    rng = random.Random(126)
    ids = [rng.randrange(CONCEPTS) for _ in range(QUERIES)]
    forward = [f"anchor{i} rel{i} object{i}" for i in ids]
    reversed_phrases = [f"object{i} rel{i} anchor{i}" for i in ids]

    t0 = time.perf_counter()
    baseline = [router.resolve_text(text) for text in forward]
    baseline_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    relational = [router.resolve_text_relational(text, relation_window=2) for text in forward]
    relational_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    reversed_results = [router.resolve_text_relational(text, relation_window=2) for text in reversed_phrases]
    reversed_s = time.perf_counter() - t0

    correct = 0
    parity = 0
    for idx, (base, rel) in enumerate(zip(baseline, relational)):
        expected = f"c{ids[idx]}"
        correct += rel.concept_id == expected
        parity += rel.concept_id == base.concept_id

    forward_relation = sum(item.relation_score for item in relational) / len(relational)
    reverse_relation = sum(item.relation_score for item in reversed_results) / len(reversed_results)
    if correct != QUERIES or parity != QUERIES:
        raise AssertionError((correct, parity, QUERIES))
    if not forward_relation > reverse_relation:
        raise AssertionError((forward_relation, reverse_relation))

    print(json.dumps({
        "concepts": CONCEPTS,
        "queries": QUERIES,
        "baseline_phrase_s": baseline_s,
        "relational_phrase_s": relational_s,
        "relational_overhead": relational_s / baseline_s if baseline_s else None,
        "reverse_relational_s": reversed_s,
        "forward_relation_mean": forward_relation,
        "reverse_relation_mean": reverse_relation,
        "directional_ratio": forward_relation / reverse_relation if reverse_relation else None,
        "accuracy": correct / QUERIES,
        "baseline_parity": parity / QUERIES,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
