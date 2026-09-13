from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory


@dataclass(frozen=True, slots=True)
class ConvergenceMatch:
    trajectory_id: str
    raw_text: str
    terminal_surface: str | None
    matched_addresses: int
    ordered_matches: int
    max_hops_to_terminal: int
    sum_hops_to_terminal: int
    route_hops: tuple[int, ...]

    @property
    def convergence_key(self) -> tuple[int, int, int, int, str]:
        # Purely structural lexicographic ranking. No learned scalar weights.
        return (
            self.matched_addresses,
            self.ordered_matches,
            -self.max_hops_to_terminal,
            -self.sum_hops_to_terminal,
            self.trajectory_id,
        )


class AddressConvergenceResolver:
    """Resolve a query by convergence inside stored occurrence trajectories.

    Reused addresses can activate many stored occurrences, but traversal is not
    allowed to jump from one experience to another merely because a common token
    address appears in both. This keeps address reuse while preserving trajectory
    continuity and avoids global-hub shortcuts.
    """

    def __init__(self, memory: AddressTrajectoryMemory) -> None:
        self.memory = memory

    @staticmethod
    def _ordered_positions(query: tuple[str, ...], candidate: tuple[str, ...]) -> int:
        # Longest common subsequence over addresses only. Query addresses absent
        # from a candidate do not poison later valid matches.
        if not query or not candidate:
            return 0
        prev = [0] * (len(candidate) + 1)
        for q in query:
            curr = [0]
            for index, c in enumerate(candidate, start=1):
                if q == c:
                    curr.append(prev[index - 1] + 1)
                else:
                    curr.append(max(curr[-1], prev[index]))
            prev = curr
        return prev[-1]

    def resolve(self, text: str, *, limit: int = 5) -> tuple[ConvergenceMatch, ...]:
        query_tokens = self.memory.decompose(text)
        query = tuple(token.address for token in query_tokens)
        if not query:
            return ()

        query_unique = tuple(dict.fromkeys(query))
        matches: list[ConvergenceMatch] = []

        for trajectory in self.memory.snapshot():
            if not trajectory.addresses:
                continue

            terminal_index = len(trajectory.addresses) - 1
            route_hops: list[int] = []

            for address in query_unique:
                positions = [
                    index
                    for index, candidate in enumerate(trajectory.addresses)
                    if candidate == address
                ]
                if not positions:
                    continue
                # Any occurrence of the same address is a valid entry point into
                # this occurrence trajectory. The shortest forward route to the
                # terminal is a discrete hop count, not a learned weight.
                best_position = max(positions)
                route_hops.append(terminal_index - best_position)

            if not route_hops:
                continue

            matches.append(
                ConvergenceMatch(
                    trajectory_id=trajectory.trajectory_id,
                    raw_text=trajectory.raw_text,
                    terminal_surface=(trajectory.surfaces[-1] if trajectory.surfaces else None),
                    matched_addresses=len(route_hops),
                    ordered_matches=self._ordered_positions(query, trajectory.addresses),
                    max_hops_to_terminal=max(route_hops),
                    sum_hops_to_terminal=sum(route_hops),
                    route_hops=tuple(sorted(route_hops)),
                )
            )

        matches.sort(key=lambda item: item.convergence_key, reverse=True)
        return tuple(matches[: max(0, limit)])
