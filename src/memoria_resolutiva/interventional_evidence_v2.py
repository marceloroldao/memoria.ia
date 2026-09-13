from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InterventionalTrial:
    trial_id: str
    context_signature: tuple[str, ...]
    intervention_address: str
    intervention_applied: bool
    target_observation: tuple[str, ...]
    provenance: str = "live.infinita"


@dataclass(frozen=True, slots=True)
class InterventionalEvidence:
    context_signature: tuple[str, ...]
    intervention_address: str
    target_observation: tuple[str, ...]
    applied_trials: tuple[str, ...]
    withdrawn_trials: tuple[str, ...]
    supported: bool
    reversible: bool
    reason: str


class InterventionalEvidenceMemory:
    """Conservative intervention-vs-withdrawal evidence store.

    This is not a causal proof engine. It only records whether the same target
    observation recurs when an intervention is deliberately applied under the
    same structural context and disappears in independent withdrawal trials.
    """

    def __init__(self) -> None:
        self._trials: list[InterventionalTrial] = []

    def observe(
        self,
        *,
        trial_id: str,
        context_signature: tuple[str, ...],
        intervention_address: str,
        intervention_applied: bool,
        target_observation: tuple[str, ...],
        provenance: str = "live.infinita",
    ) -> InterventionalTrial:
        if not trial_id or not intervention_address:
            raise ValueError("trial_id and intervention_address must be non-empty")
        if not context_signature or any(not item for item in context_signature):
            raise ValueError("context_signature must contain non-empty addresses")
        if not target_observation or any(not item for item in target_observation):
            raise ValueError("target_observation must contain non-empty addresses")
        trial = InterventionalTrial(
            trial_id=trial_id,
            context_signature=tuple(context_signature),
            intervention_address=intervention_address,
            intervention_applied=bool(intervention_applied),
            target_observation=tuple(target_observation),
            provenance=provenance,
        )
        self._trials.append(trial)
        return trial

    def resolve(
        self,
        *,
        context_signature: tuple[str, ...],
        intervention_address: str,
        target_observation: tuple[str, ...],
        min_independent_applied: int = 2,
        min_independent_withdrawn: int = 1,
    ) -> InterventionalEvidence:
        if min_independent_applied < 2:
            raise ValueError("min_independent_applied must be >= 2")
        if min_independent_withdrawn < 1:
            raise ValueError("min_independent_withdrawn must be >= 1")

        context = tuple(context_signature)
        target = tuple(target_observation)
        applied = sorted({
            item.trial_id for item in self._trials
            if item.context_signature == context
            and item.intervention_address == intervention_address
            and item.intervention_applied
            and item.target_observation == target
        })
        withdrawn_with_target = sorted({
            item.trial_id for item in self._trials
            if item.context_signature == context
            and item.intervention_address == intervention_address
            and not item.intervention_applied
            and item.target_observation == target
        })
        withdrawn_without_target = sorted({
            item.trial_id for item in self._trials
            if item.context_signature == context
            and item.intervention_address == intervention_address
            and not item.intervention_applied
            and item.target_observation != target
        })

        enough_applied = len(applied) >= min_independent_applied
        reversible = len(withdrawn_without_target) >= min_independent_withdrawn and not withdrawn_with_target

        if not enough_applied:
            reason = "insufficient-deliberate-intervention-support"
            supported = False
        elif withdrawn_with_target:
            reason = "target-persists-without-intervention"
            supported = False
            reversible = False
        elif reversible:
            reason = "deliberate-intervention-with-withdrawal-contrast"
            supported = True
        else:
            reason = "intervention-supported-without-withdrawal-evidence"
            supported = True

        return InterventionalEvidence(
            context_signature=context,
            intervention_address=intervention_address,
            target_observation=target,
            applied_trials=tuple(applied),
            withdrawn_trials=tuple(sorted(set(withdrawn_with_target) | set(withdrawn_without_target))),
            supported=supported,
            reversible=reversible,
            reason=reason,
        )

    def snapshot(self) -> tuple[InterventionalTrial, ...]:
        return tuple(self._trials)

    @classmethod
    def restore(cls, snapshot: tuple[InterventionalTrial, ...]) -> "InterventionalEvidenceMemory":
        memory = cls()
        memory._trials = list(snapshot)
        return memory
