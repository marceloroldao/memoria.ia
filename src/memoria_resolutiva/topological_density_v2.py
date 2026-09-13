from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory


@dataclass(frozen=True, slots=True)
class DensityProfile:
    address: str
    surface: str
    occurrences: int
    trajectory_count: int
    predecessor_count: int
    successor_count: int
    connection_count: int

    @property
    def topological_key(self) -> tuple[int, int, int, int, str]:
        """Structural density ordering only; no learned scalar weight."""
        return (
            self.trajectory_count,
            self.connection_count,
            self.occurrences,
            self.predecessor_count + self.successor_count,
            self.address,
        )


@dataclass(frozen=True, slots=True)
class CacheTransition:
    input_address: str
    previous_address: str | None
    accepted: bool
    reason: str


class LoopRejectingAddressCache:
    """One-step address cache that rejects immediate self-loops.

    The invariant is deliberately minimal and modality-agnostic:
    an incoming address equal to the current cache address does not advance
    state and does not create reinforcement. A different address advances state.
    """

    def __init__(self) -> None:
        self._current: str | None = None
        self._accepted = 0
        self._rejected_loops = 0

    @property
    def current(self) -> str | None:
        return self._current

    @property
    def accepted_count(self) -> int:
        return self._accepted

    @property
    def rejected_loop_count(self) -> int:
        return self._rejected_loops

    def push(self, address: str) -> CacheTransition:
        previous = self._current
        if previous == address:
            self._rejected_loops += 1
            return CacheTransition(
                input_address=address,
                previous_address=previous,
                accepted=False,
                reason="same_as_current_cache",
            )
        self._current = address
        self._accepted += 1
        return CacheTransition(
            input_address=address,
            previous_address=previous,
            accepted=True,
            reason="state_advanced",
        )


class TopologicalDensityEngine:
    """Quantify hyper-connected addresses without semantic stopword lists.

    The engine never labels a word as important/unimportant by vocabulary.
    Density emerges only from observed topology: how often the same reusable
    address occurs, in how many distinct trajectories, and how many distinct
    predecessor/successor addresses it connects.

    In the Resolutive ontology documentation, highly connected nodes may be
    described metaphorically as "topological black holes". This class makes no
    physical claim and does not require the metaphor for computation.
    """

    def __init__(self, memory: AddressTrajectoryMemory) -> None:
        self.memory = memory

    def profiles(self) -> tuple[DensityProfile, ...]:
        occurrences: dict[str, int] = defaultdict(int)
        trajectories: dict[str, set[str]] = defaultdict(set)
        predecessors: dict[str, set[str]] = defaultdict(set)
        successors: dict[str, set[str]] = defaultdict(set)
        surfaces: dict[str, str] = {}

        for trajectory in self.memory.snapshot():
            addresses = trajectory.addresses
            for index, address in enumerate(addresses):
                occurrences[address] += 1
                trajectories[address].add(trajectory.trajectory_id)
                surfaces.setdefault(address, trajectory.surfaces[index])
                if index > 0:
                    predecessors[address].add(addresses[index - 1])
                if index + 1 < len(addresses):
                    successors[address].add(addresses[index + 1])

        result: list[DensityProfile] = []
        for address in occurrences:
            neighbors = predecessors[address] | successors[address]
            result.append(
                DensityProfile(
                    address=address,
                    surface=surfaces[address],
                    occurrences=occurrences[address],
                    trajectory_count=len(trajectories[address]),
                    predecessor_count=len(predecessors[address]),
                    successor_count=len(successors[address]),
                    connection_count=len(neighbors),
                )
            )
        result.sort(key=lambda item: item.topological_key, reverse=True)
        return tuple(result)

    def densest(self, *, limit: int = 20) -> tuple[DensityProfile, ...]:
        return self.profiles()[: max(0, limit)]

    def profile_for_surface(self, surface: str) -> DensityProfile | None:
        tokens = self.memory.decompose(surface)
        if len(tokens) != 1:
            raise ValueError("surface must decompose to exactly one address")
        target = tokens[0].address
        for profile in self.profiles():
            if profile.address == target:
                return profile
        return None


def collapse_immediate_loops(memory: AddressTrajectoryMemory, text: str) -> tuple[str, ...]:
    """Return the accepted address stream after rejecting immediate repeats.

    This does not remove globally frequent nodes. It only prevents an identical
    input address from repeatedly advancing the current cache state.
    """
    cache = LoopRejectingAddressCache()
    accepted: list[str] = []
    for token in memory.decompose(text):
        transition = cache.push(token.address)
        if transition.accepted:
            accepted.append(token.address)
    return tuple(accepted)
