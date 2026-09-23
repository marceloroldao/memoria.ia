from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

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
    in the new origin string. Decision audit can be restored after restart so a
    decision id remains an idempotency boundary.
    """

    def __init__(self, evidence: EvidenceCore) -> None:
        self.evidence = evidence
        self._decision_ids: set[str] = set()
        self._decisions: list[LearningDecision] = []

    @staticmethod
    def _clean(value: str, field: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"{field} must be non-empty")
        return value

    def iter_decisions(self) -> tuple[LearningDecision, ...]:
        return tuple(self._decisions)

    def restore_decisions(self, decisions: Iterable[LearningDecision]) -> None:
        restored = tuple(decisions)
        ids = [item.decision_id for item in restored]
        if len(ids) != len(set(ids)):
            raise ValueError("learning audit contains duplicate decision_id")
        evidence_ids = {edge.evidence_id for edge in self.evidence.iter_evidence()}
        for item in restored:
            self._clean(item.decision_id, "decision_id")
            self._clean(item.candidate_evidence_id, "candidate_evidence_id")
            self._clean(item.validator_id, "validator_id")
            self._clean(item.reason, "reason")
            if item.validator_source not in _ALLOWED_VALIDATORS:
                raise ValueError("learning audit contains invalid validator source")
            if item.candidate_evidence_id not in evidence_ids:
                raise ValueError("learning decision references unknown candidate evidence")
            if item.accepted:
                if not item.promoted_evidence_id:
                    raise ValueError("accepted learning decision requires promoted evidence id")
                if item.promoted_evidence_id not in evidence_ids:
                    raise ValueError("learning decision references unknown promoted evidence")
            elif item.promoted_evidence_id is not None:
                raise ValueError("rejected learning decision cannot reference promoted evidence")
        self._decisions = list(restored)
        self._decision_ids = set(ids)

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

        if not accepted:
            decision = LearningDecision(
                decision_id,
                candidate.evidence_id,
                False,
                validator_source,
                validator_id,
                reason,
                None,
            )
            self._decision_ids.add(decision_id)
            self._decisions.append(decision)
            return decision

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
        decision = LearningDecision(
            decision_id,
            candidate.evidence_id,
            True,
            validator_source,
            validator_id,
            reason,
            promoted.evidence_id,
        )
        self._decision_ids.add(decision_id)
        self._decisions.append(decision)
        return decision
