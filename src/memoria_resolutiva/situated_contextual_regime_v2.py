from __future__ import annotations

from dataclasses import dataclass

from .contextual_temporal_regime_v2 import ContextualRegimeKey, contextual_regime_key
from .temporal_regime_state_v2 import TemporalRegimeState, observe_regime
from .world_state_candidate_resolution_v2 import WorldStateCandidate


@dataclass(frozen=True, slots=True)
class SituatedContextKey:
    """Two-scale context identity for active temporal continuity.

    `structural_key` remains literal-free and supports transfer/generalization.
    `state_signature` and `intervention_address` preserve the concrete observed
    configuration so distinct but isomorphic places/states can maintain separate
    active regimes.  No semantic labels or learned weights are introduced.
    """

    structural_key: ContextualRegimeKey
    state_signature: tuple[str, ...]
    intervention_address: str


@dataclass(frozen=True, slots=True)
class SituatedContextualRegimes:
    entries: tuple[tuple[SituatedContextKey, TemporalRegimeState], ...]

    @classmethod
    def empty(cls) -> "SituatedContextualRegimes":
        return cls(())

    def get(self, key: SituatedContextKey) -> TemporalRegimeState:
        for stored_key, state in self.entries:
            if stored_key == key:
                return state
        return TemporalRegimeState.empty()

    def with_state(
        self,
        key: SituatedContextKey,
        state: TemporalRegimeState,
    ) -> "SituatedContextualRegimes":
        items = [(k, v) for k, v in self.entries if k != key]
        items.append((key, state))
        items.sort(
            key=lambda item: (
                item[0].structural_key.state_width,
                item[0].structural_key.state_equality_pattern,
                item[0].structural_key.intervention_role,
                item[0].state_signature,
                item[0].intervention_address,
            )
        )
        return SituatedContextualRegimes(tuple(items))


def situated_context_key(
    state_addresses: tuple[str, ...],
    intervention_address: str,
) -> SituatedContextKey:
    if not state_addresses or not intervention_address:
        raise ValueError("state and intervention must be non-empty")
    return SituatedContextKey(
        structural_key=contextual_regime_key(state_addresses, intervention_address),
        state_signature=tuple(state_addresses),
        intervention_address=intervention_address,
    )


def observe_situated_regime(
    regimes: SituatedContextualRegimes,
    state_addresses: tuple[str, ...],
    intervention_address: str,
    observed_candidate: WorldStateCandidate,
    *,
    min_contiguous_support: int = 2,
) -> SituatedContextualRegimes:
    key = situated_context_key(state_addresses, intervention_address)
    current = regimes.get(key)
    updated = observe_regime(
        current,
        observed_candidate,
        min_contiguous_support=min_contiguous_support,
    )
    return regimes.with_state(key, updated)
