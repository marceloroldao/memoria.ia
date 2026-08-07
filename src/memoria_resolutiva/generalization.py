from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from .contextual import ContextAssociator


@dataclass(frozen=True, slots=True)
class GeneralizationMetrics:
    queries: int
    top1_correct: int
    top1_accuracy: float
    mean_partner_score: float
    mean_distractor_score: float
    mean_margin: float


def evaluate_pairs(
    model: ContextAssociator,
    pairs: list[tuple[str, str]],
    distractors: dict[str, list[str]] | None = None,
) -> GeneralizationMetrics:
    """Evaluate hidden contextual relations under adversarial distractors.

    Each relation is tested in both directions. The expected partner must rank
    first among all observed nodes. Margin is partner similarity minus the best
    declared distractor similarity for that query.
    """
    distractors = distractors or {}
    correct = 0
    partner_scores: list[float] = []
    distractor_scores: list[float] = []
    margins: list[float] = []

    directional = [(a, b) for a, b in pairs] + [(b, a) for a, b in pairs]
    for query, expected in directional:
        nearest = model.nearest(query, top_k=1)
        if nearest and nearest[0][0] == expected:
            correct += 1

        partner = model.similarity(query, expected)
        declared = distractors.get(query, [])
        best_distractor = max(
            (model.similarity(query, node) for node in declared),
            default=0.0,
        )
        partner_scores.append(partner)
        distractor_scores.append(best_distractor)
        margins.append(partner - best_distractor)

    queries = len(directional)
    return GeneralizationMetrics(
        queries=queries,
        top1_correct=correct,
        top1_accuracy=(correct / queries) if queries else 0.0,
        mean_partner_score=mean(partner_scores) if partner_scores else 0.0,
        mean_distractor_score=mean(distractor_scores) if distractor_scores else 0.0,
        mean_margin=mean(margins) if margins else 0.0,
    )
