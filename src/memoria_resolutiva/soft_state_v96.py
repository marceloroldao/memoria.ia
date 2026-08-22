from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .textual import TextContextMemory, tokenize
from .two_channel_v96 import EntityStateTwoChannelRouterV96
from .sentence_semantic_router_v96 import _STOPWORDS


@dataclass(frozen=True, slots=True)
class SoftStateDecision:
    concept_id: str | None
    lexical_score: float
    exact_state_hits: int
    soft_state_hits: int
    best_soft_similarity: float
    source: str


class SoftStateEvidenceRouterV96(EntityStateTwoChannelRouterV96):
    """Non-neural two-channel router with contextual soft state matching.

    Candidate selection remains sparse lexical routing. State/event validation may
    accept a query term that is not an exact training token when its contextual
    neighborhood is similar to a learned state term. Contextual similarity is
    learned only from observed training/calibration sentences through sparse
    trajectory neighborhoods; no embeddings or neural networks are used.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.07,
        min_state_score: float = 0.0,
        min_soft_similarity: float = 0.30,
        min_total_state_evidence: int = 1,
        context_radius: int = 3,
    ) -> None:
        super().__init__(
            threshold=threshold,
            min_margin=0.0,
            min_state_score=min_state_score,
            min_state_terms=1,
        )
        self.min_soft_similarity = float(min_soft_similarity)
        self.min_total_state_evidence = max(1, int(min_total_state_evidence))
        self.context = TextContextMemory(radius=context_radius)

    def observe_concept(self, concept_id: str, examples: Iterable[str]) -> None:
        examples = list(examples)
        super().observe_concept(concept_id, examples)
        self.context.observe_many(examples)

    def observe_counterexample(self, concept_id: str, sentence: str) -> None:
        super().observe_counterexample(concept_id, sentence)
        self.context.observe_sentence(sentence)

    def _query_terms(self, sentence: str) -> set[str]:
        return {t for t in tokenize(sentence) if t not in _STOPWORDS}

    def _soft_evidence(self, concept_id: str, sentence: str) -> tuple[int, int, float]:
        query_terms = self._query_terms(sentence)
        _entity_profile, state_profile = self._channels(concept_id)
        state_terms = set(state_profile)
        exact = len(query_terms & state_terms)
        remaining = query_terms - state_terms

        soft_hits = 0
        best = 0.0
        for q in remaining:
            q_best = 0.0
            for state in state_terms:
                # Unordered similarity is intentionally used here because event
                # paraphrases may change grammatical position while retaining a
                # similar local context.
                sim = self.context.unordered_similarity(q, state)
                q_best = max(q_best, sim)
            best = max(best, q_best)
            if q_best >= self.min_soft_similarity:
                soft_hits += 1
        return exact, soft_hits, best

    def resolve(self, sentence: str) -> SoftStateDecision:
        query, ranked = self.base._rank(sentence)
        if not query or not ranked:
            return SoftStateDecision(None, 0.0, 0, 0, 0.0, "unresolved")

        negated = self._negated_content_tokens(sentence)
        best_seen = ranked[0][1]
        best_exact = best_soft = 0
        best_similarity = 0.0

        for concept_id, lexical_score in ranked:
            if lexical_score < self.threshold:
                continue

            concept_profile = self.base._profiles[concept_id]
            learned_negative_relation = set(self._positive_negated_tokens.get(concept_id, ()))
            contradictory = (negated & set(concept_profile)) - learned_negative_relation
            if contradictory:
                continue

            negative_score = self._negative_score(concept_id, query)
            if (
                negative_score >= self.negative_threshold
                and lexical_score - negative_score < self.min_contrast_margin
            ):
                continue

            exact, soft, best = self._soft_evidence(concept_id, sentence)
            if (exact + soft, best) > (best_exact + best_soft, best_similarity):
                best_exact, best_soft, best_similarity = exact, soft, best

            if exact + soft < self.min_total_state_evidence:
                continue

            return SoftStateDecision(
                concept_id,
                lexical_score,
                exact,
                soft,
                best,
                "soft-state-memory",
            )

        return SoftStateDecision(
            None,
            best_seen,
            best_exact,
            best_soft,
            best_similarity,
            "soft-state-insufficient",
        )
