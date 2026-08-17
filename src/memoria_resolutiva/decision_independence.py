from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .polysemy import jaccard


@dataclass(frozen=True, slots=True)
class RawObservation:
    epoch: int
    token: str
    context: frozenset[str]


@dataclass(frozen=True, slots=True)
class ConceptDecision:
    epoch: int
    pair: tuple[str, str]
    merge_confidence: float
    decision: str  # merge | uncertain | split


class DecisionIndependentConceptMemory:
    """Keep observed evidence immutable and ontology decisions derived.

    Confidence is always recomputed from raw observations only. Previous
    merge/split decisions are never fed back as evidence, preventing the
    ontology from recursively validating itself.
    """

    def __init__(self, merge_threshold: float = 0.67, split_threshold: float = 0.33):
        self.merge_threshold = merge_threshold
        self.split_threshold = split_threshold
        self._observations: list[RawObservation] = []
        self._decisions: list[ConceptDecision] = []

    def observe(self, epoch: int, token: str, context: Iterable[str]) -> None:
        self._observations.append(RawObservation(epoch, token.lower(), frozenset(w.lower() for w in context)))

    def observations(self) -> tuple[RawObservation, ...]:
        return tuple(self._observations)

    def _contexts(self, token: str, upto_epoch: int | None = None) -> list[frozenset[str]]:
        token = token.lower()
        return [
            o.context for o in self._observations
            if o.token == token and (upto_epoch is None or o.epoch <= upto_epoch)
        ]

    def raw_merge_confidence(self, token_a: str, token_b: str, upto_epoch: int | None = None) -> float:
        ca = self._contexts(token_a, upto_epoch)
        cb = self._contexts(token_b, upto_epoch)
        if not ca or not cb:
            return 0.5

        # Compare every raw context cross-pair. No derived group or prior
        # conceptual decision contributes to this score.
        similarities = [jaccard(set(a), set(b)) for a in ca for b in cb]
        mean_similarity = sum(similarities) / len(similarities)

        # Beta-like shrinkage toward neutrality for small evidence volumes.
        support = min(len(ca), len(cb))
        shrink = support / (support + 3.0)
        return 0.5 * (1.0 - shrink) + mean_similarity * shrink

    def decide(self, epoch: int, token_a: str, token_b: str) -> ConceptDecision:
        confidence = self.raw_merge_confidence(token_a, token_b, upto_epoch=epoch)
        if confidence >= self.merge_threshold:
            label = "merge"
        elif confidence <= self.split_threshold:
            label = "split"
        else:
            label = "uncertain"
        decision = ConceptDecision(epoch, (token_a.lower(), token_b.lower()), confidence, label)
        self._decisions.append(decision)
        return decision

    def decision_history(self, token_a: str, token_b: str) -> list[ConceptDecision]:
        pair = (token_a.lower(), token_b.lower())
        reverse = (pair[1], pair[0])
        return [d for d in self._decisions if d.pair in (pair, reverse)]
