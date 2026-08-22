from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log
from typing import Iterable

from .sentence_semantic_router_v96 import SentenceSemanticRouterV96
from .textual import tokenize


_STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos",
    "e", "em", "no", "na", "nos", "nas", "por", "para", "com", "sem",
    "que", "foi", "esta", "este", "esse", "essa", "ao", "aos", "se",
    "mas", "porque", "como", "ainda", "depois", "antes", "muito", "mais",
    "menos", "ja", "nao",
}


@dataclass(frozen=True, slots=True)
class EventActionResolution:
    concept_id: str | None
    source: str
    lexical_score: float
    lexical_margin: float
    event_action_score: float
    positive_evidence: float
    negative_evidence: float
    evidence_terms: int


class EventActionContrastRouterV96:
    """Experimental sparse event-vs-action gate for v0.96.

    Concept retrieval remains separate and lexical. A second global channel learns
    which content terms are more characteristic of observed events/failures versus
    calibration actions/normal states. The second channel is a smoothed token
    log-likelihood ratio; it has no embeddings, neural network, or adversarial-test
    access.

    A candidate is accepted only when the event/action evidence exceeds a calibrated
    margin. This tests whether separating *what entity/concept is mentioned* from
    *whether an abnormal event is actually being asserted* improves open-set
    rejection.
    """

    def __init__(
        self,
        *,
        lexical_threshold: float = 0.07,
        lexical_margin: float = 0.0,
        min_event_action_score: float = 0.0,
        min_evidence_terms: int = 1,
        alpha: float = 1.0,
    ) -> None:
        if alpha <= 0:
            raise ValueError("alpha must be > 0")
        if min_evidence_terms < 0:
            raise ValueError("min_evidence_terms must be >= 0")
        self.lexical = SentenceSemanticRouterV96(
            threshold=lexical_threshold,
            min_margin=lexical_margin,
        )
        self.min_event_action_score = min_event_action_score
        self.min_evidence_terms = min_evidence_terms
        self.alpha = alpha
        self._event = Counter()
        self._action = Counter()

    @staticmethod
    def _terms(text: str) -> list[str]:
        return [t for t in tokenize(text) if t not in _STOPWORDS]

    def observe_concept(self, concept_id: str, examples: Iterable[str]) -> None:
        examples = list(examples)
        self.lexical.observe_concept(concept_id, examples)
        for sentence in examples:
            self._event.update(self._terms(sentence))

    def observe_action(self, sentence: str) -> None:
        self._action.update(self._terms(sentence))

    def _token_log_ratio(self, token: str) -> float:
        # Length-normalized multinomial likelihoods keep the two corpora comparable.
        vocab = set(self._event) | set(self._action)
        v = max(1, len(vocab))
        event_total = sum(self._event.values())
        action_total = sum(self._action.values())
        pe = (self._event[token] + self.alpha) / (event_total + self.alpha * v)
        pa = (self._action[token] + self.alpha) / (action_total + self.alpha * v)
        return log(pe / pa)

    def event_action_diagnostics(self, sentence: str) -> tuple[float, float, float, int]:
        terms = self._terms(sentence)
        if not terms:
            return 0.0, 0.0, 0.0, 0
        ratios = [self._token_log_ratio(t) for t in terms]
        positive = sum(max(0.0, r) for r in ratios)
        negative = sum(max(0.0, -r) for r in ratios)
        # Average prevents longer sentences from receiving a systematic advantage.
        score = sum(ratios) / len(ratios)
        evidence_terms = sum(1 for r in ratios if abs(r) > 1e-12)
        return score, positive, negative, evidence_terms

    def resolve(self, sentence: str) -> EventActionResolution:
        lexical = self.lexical.resolve(sentence)
        if lexical.concept_id is None:
            return EventActionResolution(
                None, "unresolved", lexical.score, lexical.margin, 0.0, 0.0, 0.0, 0
            )

        score, positive, negative, evidence_terms = self.event_action_diagnostics(sentence)
        if evidence_terms < self.min_evidence_terms:
            return EventActionResolution(
                None,
                "event-action-insufficient",
                lexical.score,
                lexical.margin,
                score,
                positive,
                negative,
                evidence_terms,
            )
        if score < self.min_event_action_score:
            return EventActionResolution(
                None,
                "action-contrast-reject",
                lexical.score,
                lexical.margin,
                score,
                positive,
                negative,
                evidence_terms,
            )
        return EventActionResolution(
            lexical.concept_id,
            "event-contrast-memory",
            lexical.score,
            lexical.margin,
            score,
            positive,
            negative,
            evidence_terms,
        )
