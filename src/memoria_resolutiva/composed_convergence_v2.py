from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.address_composition_v2 import AddressCompositionEngine, AddressComposition


@dataclass(frozen=True, slots=True)
class ComposedConvergenceMatch:
    trajectory_id: str
    terminal_surface: str | None
    matched_addresses: int
    ordered_matches: int
    max_hops_to_terminal: int
    sum_hops_to_terminal: int
    atomic_length: int
    composed_length: int

    @property
    def key(self) -> tuple[int, int, int, int, int, str]:
        return (
            self.matched_addresses,
            self.ordered_matches,
            -self.max_hops_to_terminal,
            -self.sum_hops_to_terminal,
            -self.composed_length,
            self.trajectory_id,
        )


class ComposedAddressConvergenceResolver:
    """Resolve over a derived composed-address view, never mutating raw memory."""

    def __init__(
        self,
        memory: AddressTrajectoryMemory,
        *,
        composition_engine: AddressCompositionEngine | None = None,
    ) -> None:
        self.memory = memory
        self.composition_engine = composition_engine or AddressCompositionEngine(memory)

    @staticmethod
    def _lcs(query: tuple[str, ...], candidate: tuple[str, ...]) -> int:
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

    def resolve(self, text: str, *, limit: int = 5) -> tuple[ComposedConvergenceMatch, ...]:
        catalogue: tuple[AddressComposition, ...] = self.composition_engine.discover()
        query_tokens = self.memory._collapse_immediate_tokens(self.memory.decompose(text))
        query_atomic = tuple(token.address for token in query_tokens)
        if not query_atomic:
            return ()
        query = self.composition_engine.compose_addresses(query_atomic, catalogue=catalogue)
        query_unique = tuple(dict.fromkeys(query))

        matches: list[ComposedConvergenceMatch] = []
        for trajectory in self.memory.snapshot():
            candidate = self.composition_engine.compose_addresses(
                trajectory.addresses,
                catalogue=catalogue,
            )
            if not candidate:
                continue
            terminal_index = len(candidate) - 1
            hops: list[int] = []
            for address in query_unique:
                positions = [i for i, current in enumerate(candidate) if current == address]
                if positions:
                    hops.append(terminal_index - max(positions))
            if not hops:
                continue
            matches.append(
                ComposedConvergenceMatch(
                    trajectory_id=trajectory.trajectory_id,
                    terminal_surface=(trajectory.surfaces[-1] if trajectory.surfaces else None),
                    matched_addresses=len(hops),
                    ordered_matches=self._lcs(query, candidate),
                    max_hops_to_terminal=max(hops),
                    sum_hops_to_terminal=sum(hops),
                    atomic_length=len(trajectory.addresses),
                    composed_length=len(candidate),
                )
            )

        matches.sort(key=lambda item: item.key, reverse=True)
        return tuple(matches[: max(0, limit)])
