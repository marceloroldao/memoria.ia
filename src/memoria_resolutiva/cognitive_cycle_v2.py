from __future__ import annotations

from dataclasses import dataclass

from .address_trajectory_v2 import AddressTrajectoryMemory
from .causal_state_v2 import VersionedCausalState
from .dynamic_branch_state_v2 import (
    BranchRecovery,
    BranchState,
    DynamicBranchStateResolver,
)


@dataclass(frozen=True, slots=True)
class CausalPrediction:
    """Prediction anchored to the exact evidence revision that produced it."""

    state: VersionedCausalState
    branches: BranchState

    @property
    def has_prediction(self) -> bool:
        return bool(self.branches.active)


@dataclass(frozen=True, slots=True)
class PredictionCorrection:
    """Observed correction of one historical prediction.

    The original prediction remains immutable. `corrected` is only an ephemeral
    hypothesis state after consuming the observation.
    """

    prediction: CausalPrediction
    observation_addresses: tuple[str, ...]
    corrected: BranchState
    outcome: str
    surprising: bool


@dataclass(frozen=True, slots=True)
class CognitiveRecovery:
    """Fresh retrieval after a prediction was exhausted by observation."""

    correction: PredictionCorrection
    recovery: BranchRecovery
    next_state: VersionedCausalState


class CognitiveCycleV2:
    """Minimal observation -> state -> prediction -> correction -> recovery loop.

    This layer is deliberately read-only. It does not ingest observations or
    manufacture facts. Learning policy remains separate from cognitive state.
    """

    def __init__(
        self,
        memory: AddressTrajectoryMemory,
        *,
        max_depth: int = 3,
        max_steps: int = 8,
        candidate_limit: int = 64,
        branch_limit: int = 16,
    ) -> None:
        self.memory = memory
        self.max_depth = max_depth
        self.max_steps = max_steps
        self.candidate_limit = candidate_limit
        self.branch_limit = branch_limit

    @staticmethod
    def _collapse(addresses: tuple[str, ...]) -> tuple[str, ...]:
        output: list[str] = []
        current: str | None = None
        for address in addresses:
            if address == current:
                continue
            output.append(address)
            current = address
        return tuple(output)

    def predict_addresses(
        self,
        addresses: tuple[str, ...],
        *,
        query_label: str = "<cognitive-state>",
    ) -> CausalPrediction:
        current = self._collapse(addresses)
        state = VersionedCausalState.capture(self.memory, current)

        # Prediction must use only the evidence universe frozen in `state`.
        frozen_memory = state.snapshot.materialize()
        resolver = DynamicBranchStateResolver(frozen_memory, max_depth=self.max_depth)
        branches = resolver.begin_addresses(
            current,
            query_label=query_label,
            max_steps=self.max_steps,
            candidate_limit=self.candidate_limit,
            branch_limit=self.branch_limit,
        )
        return CausalPrediction(state=state, branches=branches)

    def correct_addresses(
        self,
        prediction: CausalPrediction,
        observation_addresses: tuple[str, ...],
    ) -> PredictionCorrection:
        observation = self._collapse(observation_addresses)
        frozen_memory = prediction.state.snapshot.materialize()
        resolver = DynamicBranchStateResolver(frozen_memory, max_depth=self.max_depth)

        if not observation:
            return PredictionCorrection(
                prediction=prediction,
                observation_addresses=(),
                corrected=prediction.branches,
                outcome="no-observation",
                surprising=False,
            )

        if not prediction.has_prediction:
            return PredictionCorrection(
                prediction=prediction,
                observation_addresses=observation,
                corrected=prediction.branches,
                outcome="no-prediction",
                surprising=False,
            )

        corrected = resolver.observe_addresses(prediction.branches, observation)
        if corrected.exhausted:
            outcome = "exhausted"
            surprising = True
        elif len(corrected.active) < len(prediction.branches.active):
            outcome = "branch-reduction"
            surprising = False
        else:
            outcome = "confirmed"
            surprising = False

        return PredictionCorrection(
            prediction=prediction,
            observation_addresses=observation,
            corrected=corrected,
            outcome=outcome,
            surprising=surprising,
        )

    def recover(
        self,
        correction: PredictionCorrection,
        *,
        memory: AddressTrajectoryMemory | None = None,
        query_label: str = "<cognitive-recovery>",
    ) -> CognitiveRecovery:
        if not correction.corrected.exhausted:
            raise ValueError("recovery requires an exhausted correction")

        recovery_memory = memory if memory is not None else self.memory
        resolver = DynamicBranchStateResolver(recovery_memory, max_depth=self.max_depth)
        recovery = resolver.recover_addresses(
            correction.corrected,
            correction.observation_addresses,
            query_label=query_label,
            max_steps=self.max_steps,
            candidate_limit=self.candidate_limit,
            branch_limit=self.branch_limit,
        )
        next_state = VersionedCausalState.capture(
            recovery_memory,
            correction.prediction.state.addresses + correction.observation_addresses,
        )
        return CognitiveRecovery(
            correction=correction,
            recovery=recovery,
            next_state=next_state,
        )
