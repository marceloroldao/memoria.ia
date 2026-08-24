from __future__ import annotations

from collections import defaultdict

from memoria_resolutiva.discriminative_router_v96 import DiscriminativeSemanticRouterV96
from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96


def build(n_families: int = 20, per_family: int = 20):
    n = n_families * per_family
    sentences: list[str] = []
    concepts: list[tuple[str, str, str, str]] = []
    for family in range(n_families):
        for member in range(per_family):
            i = family * per_family + member
            anchor = f"conceito{i}"
            synonym = f"termo{i}"
            family_token = f"familia{family}"
            rare = f"assinatura{i}"
            sentences.extend([
                f"{anchor} {family_token} sistema {rare} evento{i}",
                f"{synonym} {family_token} sistema {rare} evento{i}",
            ])
            concepts.append((f"c{i}", anchor, synonym, family_token))

    full = SemanticRouterV96(threshold=0.30, min_margin=0.03, indexed=False)
    full.observe(sentences)
    routers = {
        limit: DiscriminativeSemanticRouterV96(
            threshold=0.30, min_margin=0.03, candidate_limit=limit
        )
        for limit in (8, 16, 32, 64)
    }
    for router in routers.values():
        router.observe(sentences)

    for cid, anchor, _, _ in concepts:
        full.register_concept(cid, [anchor])
        for router in routers.values():
            router.register_concept(cid, [anchor])

    return full, routers, concepts


def variants(synonym: str, family_token: str, index: int):
    rare = f"assinatura{index}"
    event = f"evento{index}"
    return {
        1.00: synonym,
        0.75: synonym,
        0.50: synonym,
        0.25: synonym,
        0.00: family_token,
    }, {
        1.00: [rare, event, family_token],
        0.75: [rare, family_token],
        0.50: [rare],
        0.25: [family_token],
        0.00: [family_token],
    }


def main():
    full, routers, concepts = build()
    totals = defaultdict(int)
    correct = defaultdict(int)
    parity = defaultdict(int)
    abstained = defaultdict(int)

    # Query tokens are learned nodes. Degradation is simulated by adding observed
    # alternative query nodes with progressively less concept-specific context.
    for idx, (cid, _anchor, synonym, family_token) in enumerate(concepts):
        _, evidence = variants(synonym, family_token, idx)
        for level, tokens in evidence.items():
            q = f"probe_{idx}_{int(level * 100)}"
            sentence = " ".join([q, *tokens])
            full.observe([sentence])
            for router in routers.values():
                router.observe([sentence])

            ref = full.resolve_token(q)
            for limit, router in routers.items():
                got = router.resolve_token(q)
                key = (level, limit)
                totals[key] += 1
                correct[key] += int(got.concept_id == cid)
                parity[key] += int(got.concept_id == ref.concept_id)
                abstained[key] += int(got.concept_id is None)

    for level in (1.00, 0.75, 0.50, 0.25, 0.00):
        for limit in (8, 16, 32, 64):
            key = (level, limit)
            total = totals[key]
            print({
                "evidence": level,
                "candidate_limit": limit,
                "accuracy": correct[key] / total,
                "parity": parity[key] / total,
                "abstention_rate": abstained[key] / total,
            })


if __name__ == "__main__":
    main()
