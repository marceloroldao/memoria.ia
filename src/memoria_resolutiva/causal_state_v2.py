from __future__ import annotations

from dataclasses import dataclass

from .address_trajectory_v2 import AddressTrajectory, AddressTrajectoryMemory
from .causal_configuration_signature_v2 import (
    CausalConfigurationSignature,
    causal_configuration_signature,
)


@dataclass(frozen=True, slots=True)
class CausalStateSnapshot:
    """Immutable evidence universe for one cognitive instant.

    A snapshot freezes which stored trajectory occurrences were available when a
    state/prediction was formed. Later ingestion may legitimately change the live
    memory's structural support, but it cannot rewrite this historical evidence
    universe retroactively.
    """

    revision: int
    trajectories: tuple[AddressTrajectory, ...]

    @classmethod
    def capture(cls, memory: AddressTrajectoryMemory) -> "CausalStateSnapshot":
        trajectories = memory.snapshot()
        return cls(revision=len(trajectories), trajectories=trajectories)

    def materialize(self) -> AddressTrajectoryMemory:
        return AddressTrajectoryMemory.restore(self.trajectories)

    def signature(
        self,
        addresses: tuple[str, ...],
        *,
        min_independent_lineages: int = 2,
        max_predecessor_diversity: int = 32,
    ) -> CausalConfigurationSignature:
        return causal_configuration_signature(
            self.materialize(),
            addresses,
            min_independent_lineages=min_independent_lineages,
            max_predecessor_diversity=max_predecessor_diversity,
        )


@dataclass(frozen=True, slots=True)
class VersionedCausalState:
    """Current configuration anchored to the evidence revision that produced it."""

    snapshot: CausalStateSnapshot
    addresses: tuple[str, ...]

    @classmethod
    def capture(
        cls,
        memory: AddressTrajectoryMemory,
        addresses: tuple[str, ...],
    ) -> "VersionedCausalState":
        return cls(CausalStateSnapshot.capture(memory), addresses)

    def signature(
        self,
        *,
        min_independent_lineages: int = 2,
        max_predecessor_diversity: int = 32,
    ) -> CausalConfigurationSignature:
        return self.snapshot.signature(
            self.addresses,
            min_independent_lineages=min_independent_lineages,
            max_predecessor_diversity=max_predecessor_diversity,
        )
