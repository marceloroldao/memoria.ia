from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import sqrt
from typing import Iterable

from .sentence_semantic_router_v96 import SentenceSemanticRouterV96, SentenceResolution


@dataclass(frozen=True, slots=True)
class ContrastiveDecision:
    concept_id: str | None
    positive_score: float
    negative_score: float
    contrast_margin: float
    source: str


class TrajectoryContrastiveRouterV96:
    """Experimental contrastive memory with independent negative trajectories.

    Positive concept memories remain aggregated by the sentence router. Negative
    evidence is stored as independent trajectories and compared locally against
    the winning concept. This avoids collapsing all counterexamples into one
    broad negative prototype.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.14,
        min_margin: float = 0.02,
        negative_threshold: float = 0.22,
        min_contrast_margin: float = 0.03,
    ) -> None:
        self.base = SentenceSemanticRouterV96(
            threshold=threshold,
            min_margin=min_margin,
        )
        self.negative_threshold = negative_threshold
        self.min_contrast_margin = min_contrast_margin
        self._negative_trajectories: dict[str, list[Counter[str]]] = defaultdict(list)

    def observe_concept(self, concept_id: str, examples: Iterable[str]) -> None:
        self.base.observe_concept(concept_id, examples)

    def observe_counterexample(self, concept_id: str, sentence: str) -> None:
        profile = self.base._content_profile(sentence)
        if profile:
            self._negative_trajectories[concept_id].append(profile)

    @staticmethod
    def _cosine(a: Counter[str], b: Counter[str]) -> float:
        if not a or not b:
            return 0.0
        shared = set(a) & set(b)
        dot = sum(a[t] * b[t] for t in shared)
        na = sqrt(sum(v * v for v in a.values()))
        nb = sqrt(sum(v * v for v in b.values()))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)

    def resolve(self, sentence: str) -> ContrastiveDecision:
        positive: SentenceResolution = self.base.resolve(sentence)
        if positive.concept_id is None:
            return ContrastiveDecision(None, positive.score, 0.0, positive.score, "unresolved")

        q = self.base._content_profile(sentence)
        negatives = self._negative_trajectories.get(positive.concept_id, ())
        negative_score = max((self._cosine(q, n) for n in negatives), default=0.0)
        contrast_margin = positive.score - negative_score

        if negative_score >= self.negative_threshold and contrast_margin < self.min_contrast_margin:
            return ContrastiveDecision(
                None,
                positive.score,
                negative_score,
                contrast_margin,
                "contrastive-reject",
            )
        return ContrastiveDecision(
            positive.concept_id,
            positive.score,
            negative_score,
            contrast_margin,
            "memory",
        )
