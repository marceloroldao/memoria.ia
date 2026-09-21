from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.address_convergence_v2 import (
    AddressConvergenceResolver,
    ConvergenceMatch,
)
from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.topological_density_v2 import TopologicalDensityEngine


@dataclass(frozen=True, slots=True)
class PortalAwareMatch:
    trajectory_id: str
    raw_text: str
    terminal_surface: str | None
    matched_addresses: int
    ordered_matches: int
    max_hops_to_terminal: int
    sum_hops_to_terminal: int
    terminal_trajectory_count: int
    terminal_connection_count: int
    terminal_occurrences: int

    @property
    def structural_key(self) -> tuple[int, int, int, int]:
        return (
            self.matched_addresses,
            self.ordered_matches,
            -self.max_hops_to_terminal,
            -self.sum_hops_to_terminal,
        )

    @property
    def terminal_density_key(self) -> tuple[int, int, int]:
        return (
            self.terminal_trajectory_count,
            self.terminal_connection_count,
            self.terminal_occurrences,
        )

    @property
    def resolution_key(self) -> tuple[int, int, int, int, int, int, int, str]:
        # Structural evidence always dominates. Density only breaks structural ties.
        # Less-dense terminals are preferred as collapse points when support is equal.
        return (
            *self.structural_key,
            -self.terminal_trajectory_count,
            -self.terminal_connection_count,
            -self.terminal_occurrences,
            self.trajectory_id,
        )


class DensityAwareConvergenceResolver:
    """Convergence resolver where hyper-connected addresses behave as portals.

    Density is not a semantic stopword rule and is not converted to a scalar
    learned weight. The resolver first compares pure structural convergence.
    Only when structural support ties does terminal topology break the tie:
    a less-connected terminal is preferred over a hyper-connected terminal.

    Therefore a dense address can still win whenever its trajectory has stronger
    structural support. The mechanism never bans or deletes dense addresses.
    """

    def __init__(self, memory: AddressTrajectoryMemory) -> None:
        self.memory = memory
        self._base = AddressConvergenceResolver(memory)

    def resolve(self, text: str, *, limit: int = 5) -> tuple[PortalAwareMatch, ...]:
        profiles = {
            profile.address: profile
            for profile in TopologicalDensityEngine(self.memory).profiles()
        }
        trajectories = {
            trajectory.trajectory_id: trajectory
            for trajectory in self.memory.snapshot()
        }

        # Ask for every structural candidate so density can break ties globally,
        # instead of only reordering a truncated prefix.
        base_matches = self._base.resolve(text, limit=len(trajectories))
        ranked: list[PortalAwareMatch] = []

        for match in base_matches:
            trajectory = trajectories.get(match.trajectory_id)
            terminal_address = (
                trajectory.addresses[-1]
                if trajectory is not None and trajectory.addresses
                else None
            )
            profile = profiles.get(terminal_address) if terminal_address else None

            ranked.append(
                PortalAwareMatch(
                    trajectory_id=match.trajectory_id,
                    raw_text=match.raw_text,
                    terminal_surface=match.terminal_surface,
                    matched_addresses=match.matched_addresses,
                    ordered_matches=match.ordered_matches,
                    max_hops_to_terminal=match.max_hops_to_terminal,
                    sum_hops_to_terminal=match.sum_hops_to_terminal,
                    terminal_trajectory_count=(profile.trajectory_count if profile else 0),
                    terminal_connection_count=(profile.connection_count if profile else 0),
                    terminal_occurrences=(profile.occurrences if profile else 0),
                )
            )

        ranked.sort(key=lambda item: item.resolution_key, reverse=True)
        return tuple(ranked[: max(0, limit)])
