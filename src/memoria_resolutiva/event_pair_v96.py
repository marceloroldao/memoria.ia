from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from .sentence_semantic_router_v96 import _STOPWORDS
from .textual import tokenize
from .two_channel_v96 import EntityStateTwoChannelRouterV96


@dataclass(frozen=True, slots=True)
class EventPairDecision:
    concept_id: str | None
    lexical_score: float
    state_score: float
    positive_pair_hits: int
    ambiguous_pair_hits: int
    source: str


class EventPairTrajectoryRouterV96(EntityStateTwoChannelRouterV96):
    """Experimental non-neural event gate based on observed term relations.

    A topic/entity word alone is not considered sufficient evidence that an event
    occurred. Positive training sentences create unordered content-token pairs.
    Counterexamples create negative pairs. Pairs seen on both sides are ambiguous
    and are removed from the event evidence channel.

    The model remains sparse and deterministic; there are no embeddings, neural
    weights or external language models. This component is research-only.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.07,
        min_state_score: float = 0.08,
        min_event_pairs: int = 1,
        strong_state_score: float = 0.30,
    ) -> None:
        super().__init__(
            threshold=threshold,
            min_margin=0.0,
            min_state_score=min_state_score,
            min_state_terms=1,
        )
        self.min_event_pairs = max(1, int(min_event_pairs))
        self.strong_state_score = float(strong_state_score)
        self._positive_pairs: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
        self._negative_pairs: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)

    @staticmethod
    def _content_tokens(sentence: str) -> list[str]:
        # Unique-per-sentence terms prevent repeated words from manufacturing pair
        # evidence. Sorting makes pair construction deterministic.
        return sorted({t for t in tokenize(sentence) if t not in _STOPWORDS})

    @classmethod
    def _pairs(cls, sentence: str) -> Counter[tuple[str, str]]:
        terms = cls._content_tokens(sentence)
        return Counter(combinations(terms, 2))

    def observe_concept(self, concept_id: str, examples: Iterable[str]) -> None:
        examples = list(examples)
        super().observe_concept(concept_id, examples)
        for sentence in examples:
            self._positive_pairs[concept_id].update(self._pairs(sentence))

    def observe_counterexample(self, concept_id: str, sentence: str) -> None:
        super().observe_counterexample(concept_id, sentence)
        self._negative_pairs[concept_id].update(self._pairs(sentence))

    def _pair_evidence(self, concept_id: str, sentence: str) -> tuple[int, int]:
        query_pairs = set(self._pairs(sentence))
        positive = set(self._positive_pairs.get(concept_id, ()))
        negative = set(self._negative_pairs.get(concept_id, ()))
        ambiguous = positive & negative
        positive_only = positive - ambiguous
        return len(query_pairs & positive_only), len(query_pairs & ambiguous)

    def resolve(self, sentence: str) -> EventPairDecision:
        query, ranked = self.base._rank(sentence)
        if not query or not ranked:
            return EventPairDecision(None, 0.0, 0.0, 0, 0, "unresolved")

        negated = self._negated_content_tokens(sentence)
        best_seen = ranked[0][1]
        best_state = 0.0
        best_pair_hits = 0
        best_ambiguous = 0

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

            _entity_profile, state_profile = self._channels(concept_id)
            state_score = self._cosine_local(query, state_profile)
            pair_hits, ambiguous_hits = self._pair_evidence(concept_id, sentence)

            best_state = max(best_state, state_score)
            best_pair_hits = max(best_pair_hits, pair_hits)
            best_ambiguous = max(best_ambiguous, ambiguous_hits)

            has_event_relation = pair_hits >= self.min_event_pairs
            has_strong_state = state_score >= self.strong_state_score
            if state_score < self.min_state_score:
                continue
            if not (has_event_relation or has_strong_state):
                continue

            return EventPairDecision(
                concept_id,
                lexical_score,
                state_score,
                pair_hits,
                ambiguous_hits,
                "event-pair-memory",
            )

        return EventPairDecision(
            None,
            best_seen,
            best_state,
            best_pair_hits,
            best_ambiguous,
            "event-relation-insufficient",
        )
