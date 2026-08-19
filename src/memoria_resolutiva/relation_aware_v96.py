from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import sqrt
from typing import Iterable

from .sentence_semantic_router_v96 import SentenceSemanticRouterV96, _STOPWORDS
from .textual import tokenize

_NEGATORS = {"nao", "sem", "nunca", "jamais"}


@dataclass(frozen=True, slots=True)
class RelationDecision:
    concept_id: str | None
    positive_score: float
    negative_score: float
    contrast_margin: float
    source: str
    rejected_by_negation: tuple[str, ...] = ()


class RelationAwareTrajectoryRouterV96:
    """Non-neural lexical router with a separate event/state consistency gate.

    The lexical channel remains the v0.96 sentence profile. Relation/state
    features are *not* mixed into the cosine vector, avoiding the score dilution
    observed in the first state-aware experiment.

    A candidate may be rejected when:
      1. the query explicitly negates a content token observed for the candidate;
      2. an independently stored negative trajectory is sufficiently similar.

    Rejected candidates are skipped and the next lexical candidate is examined.
    This permits a query such as ``fibra nao rompeu ... recepcao fraca`` to reject
    a break event before considering a loss/attenuation event.

    This is an experimental v0.96 component, not a production default.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.08,
        min_margin: float = 0.0,
        negative_threshold: float = 0.20,
        min_contrast_margin: float = 0.04,
        negation_scope: int = 3,
    ) -> None:
        self.base = SentenceSemanticRouterV96(threshold=threshold, min_margin=min_margin)
        self.threshold = threshold
        self.min_margin = min_margin
        self.negative_threshold = negative_threshold
        self.min_contrast_margin = min_contrast_margin
        self.negation_scope = max(1, int(negation_scope))
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

    def _negated_content_tokens(self, sentence: str) -> set[str]:
        raw = tokenize(sentence)
        negated: set[str] = set()
        budget = 0
        for token in raw:
            if token in _NEGATORS:
                budget = self.negation_scope
                continue
            if token in _STOPWORDS:
                continue
            if budget > 0:
                negated.add(token)
                budget -= 1
        return negated

    def _negative_score(self, concept_id: str, query: Counter[str]) -> float:
        negatives = self._negative_trajectories.get(concept_id, ())
        return max((self._cosine(query, n) for n in negatives), default=0.0)

    def resolve(self, sentence: str) -> RelationDecision:
        query, ranked = self.base._rank(sentence)
        if not query or not ranked:
            return RelationDecision(None, 0.0, 0.0, 0.0, "unresolved")

        negated = self._negated_content_tokens(sentence)
        accepted: list[tuple[str, float, float]] = []
        rejected_negation: set[str] = set()
        best_seen = ranked[0][1]
        best_negative = 0.0

        for concept_id, score in ranked:
            if score < self.threshold:
                continue

            concept_profile = self.base._profiles[concept_id]
            contradictory = tuple(sorted(negated & set(concept_profile)))
            if contradictory:
                rejected_negation.update(contradictory)
                continue

            negative_score = self._negative_score(concept_id, query)
            best_negative = max(best_negative, negative_score)
            contrast_margin = score - negative_score
            if (
                negative_score >= self.negative_threshold
                and contrast_margin < self.min_contrast_margin
            ):
                continue

            accepted.append((concept_id, score, negative_score))

        if not accepted:
            return RelationDecision(
                None,
                best_seen,
                best_negative,
                best_seen - best_negative,
                "relation-reject" if rejected_negation or best_negative else "unresolved",
                tuple(sorted(rejected_negation)),
            )

        best_id, best_score, negative_score = accepted[0]
        second_score = accepted[1][1] if len(accepted) > 1 else 0.0
        margin = best_score - second_score
        if margin < self.min_margin:
            return RelationDecision(
                None,
                best_score,
                negative_score,
                best_score - negative_score,
                "unresolved",
                tuple(sorted(rejected_negation)),
            )

        return RelationDecision(
            best_id,
            best_score,
            negative_score,
            best_score - negative_score,
            "relation-memory",
            tuple(sorted(rejected_negation)),
        )
