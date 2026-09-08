from __future__ import annotations

from dataclasses import dataclass

from .evidence_core import EvidenceCore, EvidenceEdge
from .evidence_temporal_bridge import EpistemicSource, classify_epistemic_source


_ALLOWED_VALIDATORS = frozenset({
    EpistemicSource.USER_CONFIRMED,
    EpistemicSource.SENSOR_OBSERVED,
})


@dataclass(frozen=True, slots=True)
class LearningDecision:
    decision_id: str
    candidate_evidence_id: str
    accepted: bool
    validator_source: EpistemicSource
    validator_id: str
    reason: str
    promoted_evidence_id: str | None = None


class EpistemicLearningGate:
    """Explicit gate between untrusted candidates and trusted factual evidence.

    The gate never rewrites a candidate EvidenceEdge. Acceptance creates a new
    EvidenceCore edge with trusted provenance, preserving the original candidate id
    in the new origin string. This prevents provenance laundering while giving the
    temporal bridge a normal trusted evidence row to project.
    """

    def __init__(self, evidence: EvidenceCore) -> None:
        self.evidence = evidence
        self._decision_ids: set[str] = set()

    @staticmethod
    def _clean(value: str, field: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"{field} must be non-empty")
        return value

    def decide(
        self,
        candidate: EvidenceEdge,
        *,
        decision_id: str,
        accepted: bool,
        validator_source: EpistemicSource,
        validator_id: str,
        reason: str,
        promoted_evidence_id: str | None = None,
    ) -> LearningDecision:
        decision_id = self._clean(decision_id, "decision_id")
        validator_id = self._clean(validator_id, "validator_id")
        reason = self._clean(reason, "reason")
        if decision_id in self._decision_ids:
            raise ValueError("decision_id has already been applied")
        if validator_source not in _ALLOWED_VALIDATORS:
            raise ValueError("learning decisions require USER_CONFIRMED or SENSOR_OBSERVED validation")

        self._decision_ids.add(decision_id)
        if not accepted:
            return LearningDecision(
                decision_id,
                candidate.evidence_id,
                False,
                validator_source,
                validator_id,
                reason,
                None,
            )

        if promoted_evidence_id is None:
            promoted_evidence_id = f"learning:{decision_id}"
        promoted_evidence_id = self._clean(promoted_evidence_id, "promoted_evidence_id")

        # Do not mutate/reclassify the candidate. Create a separate validated fact.
        source_class = classify_epistemic_source(candidate)
        promoted = self.evidence.observe_relation(
            candidate.subject,
            candidate.predicate,
            candidate.object,
            evidence_id=promoted_evidence_id,
            source_text=candidate.source_text,
            provenance=validator_source.value,
            origin=(
                f"learning-gate:{validator_id};candidate={candidate.evidence_id};"
                f"candidate_source={source_class.value};decision={decision_id}"
            ),
            confidence=1.0,
            namespace=candidate.namespace,
        )
        return LearningDecision(
            decision_id,
            candidate.evidence_id,
            True,
            validator_source,
            validator_id,
            reason,
            promoted.evidence_id,
        )
