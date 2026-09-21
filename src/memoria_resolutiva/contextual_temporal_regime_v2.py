from __future__ import annotations

from dataclasses import dataclass

from .structural_intervention_transfer_v2 import _equality_pattern
from .temporal_regime_state_v2 import TemporalRegimeState, observe_regime
from .world_state_candidate_resolution_v2 import WorldStateCandidate


@dataclass(frozen=True, slots=True)
class ContextualRegimeKey:
    """Literal-free context key for one local temporal regime.

    Context identity is based only on the current state's ordered equality topology
    plus the intervention role relative to that state. This keeps regime tracking
    separate across structurally different contexts without requiring semantic labels.
    """

    state_width: int
    state_equality_pattern: tuple[int, ...]
    intervention_role: str


@dataclass(frozen=True, slots=True)
class ContextualTemporalRegimes:
    entries: tuple[tuple[ContextualRegimeKey, TemporalRegimeState], ...]

    @classmethod
    def empty(cls) -> "ContextualTemporalRegimes":
        return cls(())

    def get(self, key: ContextualRegimeKey) -> TemporalRegimeState:
        for stored_key, state in self.entries:
            if stored_key == key:
                return state
        return TemporalRegimeState.empty()

    def with_state(
        self,
        key: ContextualRegimeKey,
        state: TemporalRegimeState,
    ) -> "ContextualTemporalRegimes":
        updated = [(stored_key, stored_state) for stored_key, stored_state in self.entries if stored_key != key]
        updated.append((key, state))
        updated.sort(key=lambda item: (item[0].state_width, item[0].state_equality_pattern, item[0].intervention_role))
        return ContextualTemporalRegimes(tuple(updated))


def contextual_regime_key(
    state_addresses: tuple[str, ...],
    intervention_address: str,
) -> ContextualRegimeKey:
    if not state_addresses or not intervention_address:
        raise ValueError("state and intervention must be non-empty")

    if intervention_address in state_addresses:
        role = f"state-position:{state_addresses.index(intervention_address)}"
    else:
        role = "novel-to-state"

    return ContextualRegimeKey(
        state_width=len(state_addresses),
        state_equality_pattern=_equality_pattern(state_addresses),
        intervention_role=role,
    )


def observe_contextual_regime(
    regimes: ContextualTemporalRegimes,
    state_addresses: tuple[str, ...],
    intervention_address: str,
    observed_candidate: WorldStateCandidate,
    *,
    min_contiguous_support: int = 2,
) -> ContextualTemporalRegimes:
    key = contextual_regime_key(state_addresses, intervention_address)
    current = regimes.get(key)
    next_state = observe_regime(
        current,
        observed_candidate,
        min_contiguous_support=min_contiguous_support,
    )
    return regimes.with_state(key, next_state)
