from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .sentence_semantic_router_v96 import SentenceResolution, SentenceSemanticRouterV96


@dataclass(frozen=True, slots=True)
class ContrastiveDiagnostics:
    positive_concept_id: str | None
    positive_score: float
    negative_score: float
    contrast_margin: float
    accepted: bool


class ContrastiveSentenceSemanticRouterV96(SentenceSemanticRouterV96):
    """Experimental open-set guard based on learned counterexamples.

    Positive concept profiles are inherited from SentenceSemanticRouterV96.
    Each concept may also accumulate a sparse negative profile containing
    examples that are lexically/semantically adjacent to that concept but must
    not be resolved as the concept. No embeddings or neural network are used.

    This models online correction explicitly: a false-positive can be observed as
    a counterexample without rewriting the positive memory.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.14,
        min_margin: float = 0.02,
        min_contrast_margin: float = 0.02,
    ) -> None:
        super().__init__(threshold=threshold, min_margin=min_margin)
        self.min_contrast_margin = min_contrast_margin
        self._negative_profiles: dict[str, Counter[str]] = {}

    def observe_counterexamples(self, concept_id: str, examples: Iterable[str]) -> None:
        if concept_id not in self._profiles:
            raise KeyError(f"unknown concept_id: {concept_id}")
        profile = self._negative_profiles.setdefault(concept_id, Counter())
        count = 0
        for sentence in examples:
            profile.update(self._content_profile(sentence))
            count += 1
        if count == 0:
            raise ValueError("counterexamples must not be empty")

    def contrastive_diagnostics(self, sentence: str) -> ContrastiveDiagnostics:
        base = super().resolve(sentence)
        if base.concept_id is None:
            return ContrastiveDiagnostics(None, base.score, 0.0, base.score, False)
        query = self._content_profile(sentence)
        negative = self._negative_profiles.get(base.concept_id)
        negative_score = self._score(query, negative) if negative else 0.0
        contrast = base.score - negative_score
        return ContrastiveDiagnostics(
            positive_concept_id=base.concept_id,
            positive_score=base.score,
            negative_score=negative_score,
            contrast_margin=contrast,
            accepted=contrast >= self.min_contrast_margin,
        )

    def resolve(self, sentence: str) -> SentenceResolution:
        base = super().resolve(sentence)
        if base.concept_id is None:
            return base
        query = self._content_profile(sentence)
        negative = self._negative_profiles.get(base.concept_id)
        if not negative:
            return base
        negative_score = self._score(query, negative)
        contrast = base.score - negative_score
        if contrast < self.min_contrast_margin:
            return SentenceResolution(None, base.score, base.margin, "contrastive-unresolved")
        return SentenceResolution(base.concept_id, base.score, base.margin, "contrastive-memory")
