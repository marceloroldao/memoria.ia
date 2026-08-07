from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .contextual import ContextAssociator


@dataclass(frozen=True, slots=True)
class AssociationMetrics:
    queries: int
    top1_correct: int
    topk_correct: int
    top1_accuracy: float
    topk_recall: float


def evaluate_hidden_pairs(
    associator: ContextAssociator,
    pairs: Iterable[tuple[str, str]],
    candidate_nodes: Iterable[str] | None = None,
    top_k: int = 3,
) -> AssociationMetrics:
    pairs = list(pairs)
    expected: dict[str, str] = {}
    for a, b in pairs:
        expected[a] = b
        expected[b] = a

    candidates = list(candidate_nodes or expected.keys())
    top1 = 0
    topk = 0

    for query, target in expected.items():
        ranked = sorted(
            (
                (candidate, associator.similarity(query, candidate))
                for candidate in candidates
                if candidate != query
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        if ranked and ranked[0][0] == target:
            top1 += 1
        if target in [node for node, _ in ranked[:top_k]]:
            topk += 1

    queries = len(expected)
    return AssociationMetrics(
        queries=queries,
        top1_correct=top1,
        topk_correct=topk,
        top1_accuracy=(top1 / queries) if queries else 0.0,
        topk_recall=(topk / queries) if queries else 0.0,
    )
