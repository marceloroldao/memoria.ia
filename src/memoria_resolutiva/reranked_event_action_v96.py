from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import sqrt
from typing import Iterable

from .event_action_v96 import EventActionContrastRouterV96
from .sentence_semantic_router_v96 import SentenceSemanticRouterV96


@dataclass(frozen=True, slots=True)
class RerankedEventActionDecision:
    concept_id: str | None
    source: str
    positive_score: float
    negative_score: float
    reranked_score: float
    reranked_margin: float
    event_action_score: float


class RerankedEventActionRouterV96:
    """Low-threshold retrieval, concept contrastive reranking, then event/action gate.

    This experiment deliberately separates three decisions:
    1. broad sparse retrieval keeps paraphrase recall high;
    2. concept-specific negative trajectories rerank neighboring known classes;
    3. a global event-vs-action memory rejects normal operations/open-set mentions.

    No embeddings or neural networks are used. Counterexamples only affect the
    concept they were observed against and never rewrite positive concept memory.
    """

    def __init__(
        self,
        *,
        retrieval_threshold: float = 0.07,
        rerank_lambda: float = 0.5,
        min_reranked_score: float = 0.02,
        min_reranked_margin: float = 0.0,
        min_event_action_score: float = -0.20,
    ) -> None:
        self.retrieval_threshold = retrieval_threshold
        self.rerank_lambda = rerank_lambda
        self.min_reranked_score = min_reranked_score
        self.min_reranked_margin = min_reranked_margin
        self.base = SentenceSemanticRouterV96(threshold=0.0, min_margin=0.0)
        self.event_action = EventActionContrastRouterV96(
            lexical_threshold=0.0,
            lexical_margin=0.0,
            min_event_action_score=min_event_action_score,
            min_evidence_terms=0,
        )
        self.min_event_action_score = min_event_action_score
        self._negative: dict[str, list[Counter[str]]] = defaultdict(list)

    def observe_concept(self, concept_id: str, examples: Iterable[str]) -> None:
        examples = list(examples)
        self.base.observe_concept(concept_id, examples)
        self.event_action.observe_concept(concept_id, examples)

    def observe_counterexample(self, concept_id: str, sentence: str) -> None:
        if concept_id not in self.base._profiles:
            raise KeyError(f"unknown concept_id: {concept_id}")
        profile = self.base._content_profile(sentence)
        if profile:
            self._negative[concept_id].append(profile)
        self.event_action.observe_action(sentence)

    def observe_action(self, sentence: str) -> None:
        self.event_action.observe_action(sentence)

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

    def resolve(self, sentence: str) -> RerankedEventActionDecision:
        query, ranked = self.base._rank(sentence)
        if not query or not ranked or ranked[0][1] < self.retrieval_threshold:
            top = ranked[0][1] if ranked else 0.0
            return RerankedEventActionDecision(None, "unresolved", top, 0.0, top, 0.0, 0.0)

        reranked: list[tuple[str, float, float, float]] = []
        for concept_id, positive_score in ranked:
            negatives = self._negative.get(concept_id, ())
            negative_score = max((self._cosine(query, n) for n in negatives), default=0.0)
            adjusted = positive_score - self.rerank_lambda * negative_score
            reranked.append((concept_id, adjusted, positive_score, negative_score))
        reranked.sort(key=lambda x: (-x[1], -x[2], x[0]))

        best_id, best_adjusted, best_positive, best_negative = reranked[0]
        second_adjusted = reranked[1][1] if len(reranked) > 1 else 0.0
        margin = best_adjusted - second_adjusted
        if best_adjusted < self.min_reranked_score or margin < self.min_reranked_margin:
            return RerankedEventActionDecision(
                None, "rerank-reject", best_positive, best_negative,
                best_adjusted, margin, 0.0,
            )

        event_score, _, _, _ = self.event_action.event_action_diagnostics(sentence)
        if event_score < self.min_event_action_score:
            return RerankedEventActionDecision(
                None, "action-contrast-reject", best_positive, best_negative,
                best_adjusted, margin, event_score,
            )
        return RerankedEventActionDecision(
            best_id, "reranked-event-memory", best_positive, best_negative,
            best_adjusted, margin, event_score,
        )
