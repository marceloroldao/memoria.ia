from __future__ import annotations

from dataclasses import dataclass

from .continuous_causal_pipeline_v2 import (
    ContinuousCausalHypothesis,
    ContinuousCausalPipelineV2,
)
from .interventional_evidence_v2 import (
    InterventionalEvidence,
    InterventionalEvidenceMemory,
)


@dataclass(frozen=True, slots=True)
class InterventionalCausalAssessment:
    observational: ContinuousCausalHypothesis
    interventional: InterventionalEvidence
    level: str
    supported: bool
    reversible: bool
    reason: str


class InterventionalCausalPipelineV2:
    """Compose observational and deliberate-intervention evidence without scalar scores.

    Evidence levels are explicit and ordinal:
      observational -> intervention-supported -> reversible-intervention-supported.

    A deliberate intervention cannot rescue a path that failed the bounded temporal
    recurrence / negative-control gate, and observational recurrence cannot be promoted
    to interventional support without independent deliberate trials.
    """

    def __init__(
        self,
        observational: ContinuousCausalPipelineV2 | None = None,
        interventions: InterventionalEvidenceMemory | None = None,
        *,
        min_independent_applied: int = 2,
        min_independent_withdrawn: int = 1,
    ) -> None:
        if min_independent_applied < 2:
            raise ValueError("min_independent_applied must be >= 2")
        if min_independent_withdrawn < 1:
            raise ValueError("min_independent_withdrawn must be >= 1")
        self.observational = observational if observational is not None else ContinuousCausalPipelineV2()
        self.interventions = interventions if interventions is not None else InterventionalEvidenceMemory()
        self.min_independent_applied = min_independent_applied
        self.min_independent_withdrawn = min_independent_withdrawn

    def observe_interventional_trial(
        self,
        *,
        trial_id: str,
        context_signature: tuple[str, ...],
        intervention_address: str,
        intervention_applied: bool,
        target_observation: tuple[str, ...],
        provenance: str = "live.infinita",
    ) -> None:
        self.interventions.observe(
            trial_id=trial_id,
            context_signature=context_signature,
            intervention_address=intervention_address,
            intervention_applied=intervention_applied,
            target_observation=target_observation,
            provenance=provenance,
        )

    def assess(
        self,
        *,
        source_address: str,
        target_address: str,
        context_signature: tuple[str, ...],
        mediator_addresses: tuple[str, ...] = (),
    ) -> InterventionalCausalAssessment:
        observational = self.observational.resolve(
            source_address=source_address,
            target_address=target_address,
            mediator_addresses=mediator_addresses,
        )
        interventional = self.interventions.resolve(
            context_signature=context_signature,
            intervention_address=source_address,
            target_observation=(target_address,),
            min_independent_applied=self.min_independent_applied,
            min_independent_withdrawn=self.min_independent_withdrawn,
        )

        if not observational.supported:
            return InterventionalCausalAssessment(
                observational=observational,
                interventional=interventional,
                level="unsupported",
                supported=False,
                reversible=False,
                reason="observational-gate-not-satisfied",
            )
        if not interventional.supported:
            return InterventionalCausalAssessment(
                observational=observational,
                interventional=interventional,
                level="observational",
                supported=True,
                reversible=False,
                reason=interventional.reason,
            )
        if interventional.reversible:
            return InterventionalCausalAssessment(
                observational=observational,
                interventional=interventional,
                level="reversible-intervention-supported",
                supported=True,
                reversible=True,
                reason="observational-and-reversible-interventional-evidence",
            )
        return InterventionalCausalAssessment(
            observational=observational,
            interventional=interventional,
            level="intervention-supported",
            supported=True,
            reversible=False,
            reason="observational-and-interventional-evidence",
        )
