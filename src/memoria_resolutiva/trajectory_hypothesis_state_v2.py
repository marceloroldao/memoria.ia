from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory, AddressTrajectory
from memoria_resolutiva.multiscale_resolver_v2 import MultiscaleAddressResolver


@dataclass(frozen=True, slots=True)
class ActiveTrajectoryHypothesis:
    trajectory_id: str
    cursor: int
    matched_observations: int
    supporting_depths: tuple[int, ...]
    remaining_addresses: tuple[str, ...]
    remaining_surfaces: tuple[str | None, ...]


@dataclass(frozen=True, slots=True)
class HypothesisState:
    seed_query: str
    observations: tuple[str, ...]
    active: tuple[ActiveTrajectoryHypothesis, ...]
    eliminated_trajectory_ids: tuple[str, ...]
    shared_next_addresses: tuple[str, ...]
    shared_next_surfaces: tuple[str | None, ...]
    collapsed_trajectory_id: str | None
    ambiguous: bool
    contradiction: bool


class IncrementalTrajectoryHypothesisResolver:
    """Maintain competing trajectory hypotheses as observations arrive.

    A hypothesis is an occurrence trajectory plus a cursor into that occurrence.
    New observations may advance or eliminate hypotheses, but never reinforce a
    scalar score, create a fact, or jump through a shared address into another
    trajectory. Equal surviving alternatives remain explicit.
    """

    def __init__(
        self,
        memory: AddressTrajectoryMemory,
        seed_query: str,
        *,
        max_depth: int = 3,
        candidate_limit: int = 64,
        shared_lookahead: int = 8,
    ) -> None:
        if shared_lookahead < 1:
            raise ValueError("shared_lookahead must be >= 1")
        self.memory = memory
        self.seed_query = seed_query
        self.shared_lookahead = shared_lookahead
        self._observations: list[str] = []
        self._eliminated: set[str] = set()
        self._by_id = {t.trajectory_id: t for t in memory.snapshot()}

        resolver = MultiscaleAddressResolver(memory, max_depth=max_depth)
        matches = resolver.resolve(seed_query, limit=max(candidate_limit, 1))
        query = self._addresses(seed_query)
        self._active: dict[str, tuple[int, int, tuple[int, ...]]] = {}
        for match in matches:
            trajectory = self._by_id.get(match.trajectory_id)
            if trajectory is None:
                continue
            cursor = self._cursor_after_seed(trajectory, query)
            if cursor is None:
                continue
            self._active[trajectory.trajectory_id] = (cursor, 0, match.supporting_depths)

    def _addresses(self, text: str) -> tuple[str, ...]:
        tokens = self.memory._collapse_immediate_tokens(self.memory.decompose(text))
        return tuple(token.address for token in tokens)

    @staticmethod
    def _cursor_after_seed(
        trajectory: AddressTrajectory,
        query: tuple[str, ...],
    ) -> int | None:
        if not query:
            return None
        query_set = set(query)
        matched_positions = [
            index for index, address in enumerate(trajectory.addresses)
            if address in query_set
        ]
        if not matched_positions:
            return None
        return max(matched_positions) + 1

    @staticmethod
    def _advance_if_compatible(
        trajectory: AddressTrajectory,
        cursor: int,
        observation: tuple[str, ...],
    ) -> int | None:
        """Advance only inside the same occurrence trajectory.

        The observation must match the next unresolved addresses in order. Leading
        addresses already passed in the trajectory are ignored only when they are
        not part of the unresolved suffix. No cross-trajectory search is allowed.
        """
        if not observation:
            return cursor
        remaining = trajectory.addresses[cursor:]
        if len(remaining) < len(observation):
            return None
        if remaining[: len(observation)] != observation:
            return None
        return cursor + len(observation)

    def observe(self, text: str) -> HypothesisState:
        observation = self._addresses(text)
        self._observations.append(text)

        survivors: dict[str, tuple[int, int, tuple[int, ...]]] = {}
        for trajectory_id, (cursor, matched_count, depths) in self._active.items():
            trajectory = self._by_id[trajectory_id]
            advanced = self._advance_if_compatible(trajectory, cursor, observation)
            if advanced is None:
                self._eliminated.add(trajectory_id)
                continue
            survivors[trajectory_id] = (advanced, matched_count + 1, depths)
        self._active = survivors
        return self.state()

    @staticmethod
    def _common_prefix(
        sequences: tuple[tuple[tuple[str, ...], tuple[str | None, ...]], ...],
        limit: int,
    ) -> tuple[tuple[str, ...], tuple[str | None, ...]]:
        if not sequences:
            return (), ()
        min_len = min(min(len(addresses), limit) for addresses, _ in sequences)
        length = 0
        for index in range(min_len):
            address = sequences[0][0][index]
            if all(addresses[index] == address for addresses, _ in sequences[1:]):
                length += 1
            else:
                break
        surfaces: list[str | None] = []
        for index in range(length):
            surfaces.append(next((s[index] for _, s in sequences if s[index] is not None), None))
        return sequences[0][0][:length], tuple(surfaces)

    def state(self) -> HypothesisState:
        active: list[ActiveTrajectoryHypothesis] = []
        sequences: list[tuple[tuple[str, ...], tuple[str | None, ...]]] = []
        for trajectory_id, (cursor, matched_count, depths) in sorted(self._active.items()):
            trajectory = self._by_id[trajectory_id]
            remaining_addresses = trajectory.addresses[cursor:]
            remaining_surfaces = tuple(
                trajectory.surfaces[index] if index < len(trajectory.surfaces) else None
                for index in range(cursor, len(trajectory.addresses))
            )
            active.append(
                ActiveTrajectoryHypothesis(
                    trajectory_id=trajectory_id,
                    cursor=cursor,
                    matched_observations=matched_count,
                    supporting_depths=depths,
                    remaining_addresses=remaining_addresses,
                    remaining_surfaces=remaining_surfaces,
                )
            )
            sequences.append((remaining_addresses, remaining_surfaces))

        prefix_addresses, prefix_surfaces = self._common_prefix(
            tuple(sequences), self.shared_lookahead
        )
        collapsed = active[0].trajectory_id if len(active) == 1 else None
        contradiction = len(active) == 0 and bool(self._observations)
        return HypothesisState(
            seed_query=self.seed_query,
            observations=tuple(self._observations),
            active=tuple(active),
            eliminated_trajectory_ids=tuple(sorted(self._eliminated)),
            shared_next_addresses=prefix_addresses,
            shared_next_surfaces=prefix_surfaces,
            collapsed_trajectory_id=collapsed,
            ambiguous=len(active) > 1,
            contradiction=contradiction,
        )
