from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import sqrt
from typing import Iterable

from .relation_aware_v96 import RelationAwareTrajectoryRouterV96


@dataclass(frozen=True, slots=True)
class TwoChannelDecision:
    concept_id: str | None
    lexical_score: float
    entity_score: float
    state_score: float
    source: str


class EntityStateTwoChannelRouterV96(RelationAwareTrajectoryRouterV96):
    """Experimental non-neural router separating entity from event/state evidence.

    The entity channel is learned, not hand-written. For each concept, tokens that
    occur in both positive memories and independent counterexamples are treated as
    entity/context terms: they identify what the sentence is about but do not prove
    that the remembered event is occurring. Tokens unique to positive memories form
    the state/event channel.

    For concepts without counterexamples, globally shared positive terms are also
    treated as weak entity/context terms because they are non-discriminative across
    concepts. Acceptance requires lexical plausibility plus minimum state evidence.
    This keeps the original sparse/trajectory representation and uses no neural
    embeddings or external language model.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.07,
        min_margin: float = 0.0,
        negative_threshold: float = 0.20,
        min_contrast_margin: float = 0.04,
        min_state_score: float = 0.12,
        min_state_terms: int = 1,
    ) -> None:
        super().__init__(
            threshold=threshold,
            min_margin=min_margin,
            negative_threshold=negative_threshold,
            min_contrast_margin=min_contrast_margin,
        )
        self.min_state_score = float(min_state_score)
        self.min_state_terms = max(1, int(min_state_terms))
        self._negative_union: dict[str, Counter[str]] = defaultdict(Counter)

    def observe_counterexample(self, concept_id: str, sentence: str) -> None:
        super().observe_counterexample(concept_id, sentence)
        profile = self.base._content_profile(sentence)
        self._negative_union[concept_id].update(profile)

    def _global_shared_terms(self) -> set[str]:
        owners: Counter[str] = Counter()
        for profile in self.base._profiles.values():
            for token in profile:
                owners[token] += 1
        return {token for token, count in owners.items() if count >= 2}

    def _channels(self, concept_id: str) -> tuple[Counter[str], Counter[str]]:
        positive = self.base._profiles[concept_id]
        negative = self._negative_union.get(concept_id, Counter())
        entity_terms = (set(positive) & set(negative)) | self._global_shared_terms()
        entity = Counter({t: positive[t] for t in entity_terms if t in positive})
        state = Counter({t: v for t, v in positive.items() if t not in entity_terms})
        return entity, state

    @staticmethod
    def _cosine_local(a: Counter[str], b: Counter[str]) -> float:
        if not a or not b:
            return 0.0
        shared = set(a) & set(b)
        dot = sum(a[t] * b[t] for t in shared)
        na = sqrt(sum(v * v for v in a.values()))
        nb = sqrt(sum(v * v for v in b.values()))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)

    def resolve(self, sentence: str) -> TwoChannelDecision:
        query, ranked = self.base._rank(sentence)
        if not query or not ranked:
            return TwoChannelDecision(None, 0.0, 0.0, 0.0, "unresolved")

        negated = self._negated_content_tokens(sentence)
        accepted: list[tuple[str, float, float, float]] = []

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

            entity_profile, state_profile = self._channels(concept_id)
            entity_score = self._cosine_local(query, entity_profile)
            state_score = self._cosine_local(query, state_profile)
            shared_state_terms = len(set(query) & set(state_profile))
            if shared_state_terms < self.min_state_terms or state_score < self.min_state_score:
                continue

            accepted.append((concept_id, lexical_score, entity_score, state_score))

        if not accepted:
            best_id, best_lexical = ranked[0]
            entity_profile, state_profile = self._channels(best_id)
            return TwoChannelDecision(
                None,
                best_lexical,
                self._cosine_local(query, entity_profile),
                self._cosine_local(query, state_profile),
                "state-insufficient",
            )

        best_id, lexical_score, entity_score, state_score = accepted[0]
        return TwoChannelDecision(
            best_id,
            lexical_score,
            entity_score,
            state_score,
            "two-channel-memory",
        )
