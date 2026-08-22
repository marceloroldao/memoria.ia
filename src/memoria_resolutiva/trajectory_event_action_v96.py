from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .event_action_v96 import EventActionContrastRouterV96
from .trajectory_contrastive_v96 import TrajectoryContrastiveRouterV96


@dataclass(frozen=True, slots=True)
class TrajectoryEventActionDecision:
    concept_id: str | None
    source: str
    positive_score: float
    negative_score: float
    contrast_margin: float
    event_action_score: float
    positive_evidence: float
    negative_evidence: float
    evidence_terms: int


class TrajectoryEventActionRouterV96:
    """Hybrid v0.96 candidate router + global event/action rejection channel.

    Concept identity is proposed by the trajectory-contrastive memory. A separate
    sparse event/action log-ratio gate then decides whether the sentence asserts an
    abnormal event at all. The two memories are trained only from TRAIN and
    calibration counterexamples.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.12,
        min_margin: float = 0.02,
        negative_threshold: float = 0.20,
        min_contrast_margin: float = 0.04,
        min_event_action_score: float = -0.20,
        min_evidence_terms: int = 1,
    ) -> None:
        self.candidate = TrajectoryContrastiveRouterV96(
            threshold=threshold,
            min_margin=min_margin,
            negative_threshold=negative_threshold,
            min_contrast_margin=min_contrast_margin,
        )
        # Its lexical channel is not used for decisions here; this object stores the
        # event/action corpus and exposes the diagnostics implementation.
        self.event_action = EventActionContrastRouterV96(
            lexical_threshold=threshold,
            lexical_margin=min_margin,
            min_event_action_score=min_event_action_score,
            min_evidence_terms=min_evidence_terms,
        )
        self.min_event_action_score = min_event_action_score
        self.min_evidence_terms = min_evidence_terms

    def observe_concept(self, concept_id: str, examples: Iterable[str]) -> None:
        examples = list(examples)
        self.candidate.observe_concept(concept_id, examples)
        self.event_action.observe_concept(concept_id, examples)

    def observe_counterexample(self, concept_id: str, sentence: str) -> None:
        self.candidate.observe_counterexample(concept_id, sentence)
        self.event_action.observe_action(sentence)

    def observe_action(self, sentence: str) -> None:
        self.event_action.observe_action(sentence)

    def resolve(self, sentence: str) -> TrajectoryEventActionDecision:
        candidate = self.candidate.resolve(sentence)
        if candidate.concept_id is None:
            return TrajectoryEventActionDecision(
                None,
                candidate.source,
                candidate.positive_score,
                candidate.negative_score,
                candidate.contrast_margin,
                0.0,
                0.0,
                0.0,
                0,
            )

        score, positive, negative, evidence_terms = self.event_action.event_action_diagnostics(sentence)
        if evidence_terms < self.min_evidence_terms:
            return TrajectoryEventActionDecision(
                None, "event-action-insufficient", candidate.positive_score,
                candidate.negative_score, candidate.contrast_margin, score,
                positive, negative, evidence_terms,
            )
        if score < self.min_event_action_score:
            return TrajectoryEventActionDecision(
                None, "action-contrast-reject", candidate.positive_score,
                candidate.negative_score, candidate.contrast_margin, score,
                positive, negative, evidence_terms,
            )
        return TrajectoryEventActionDecision(
            candidate.concept_id, "trajectory-event-memory", candidate.positive_score,
            candidate.negative_score, candidate.contrast_margin, score,
            positive, negative, evidence_terms,
        )
