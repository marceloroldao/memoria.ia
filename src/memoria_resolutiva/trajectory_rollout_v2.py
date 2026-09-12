from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory, AddressTrajectory
from memoria_resolutiva.multiscale_resolver_v2 import MultiscaleAddressResolver


@dataclass(frozen=True, slots=True)
class RolloutPath:
    trajectory_ids: tuple[str, ...]
    continuation_addresses: tuple[str, ...]
    continuation_surfaces: tuple[str | None, ...]
    supporting_depths: tuple[int, ...]
    matched_addresses: tuple[str, ...]

    @property
    def structural_key(self) -> tuple[int, int, int, int, tuple[str, ...]]:
        return (
            len(self.matched_addresses),
            len(self.supporting_depths),
            len(self.trajectory_ids),
            len(self.continuation_addresses),
            self.continuation_addresses,
        )


@dataclass(frozen=True, slots=True)
class RolloutResolution:
    query: str
    shared_prefix_addresses: tuple[str, ...]
    shared_prefix_surfaces: tuple[str | None, ...]
    branches: tuple[RolloutPath, ...]
    divergence_index: int | None
    exhausted: bool


class TrajectoryRolloutResolver:
    """Follow compatible stored trajectories beyond a one-step frontier.

    The resolver preserves occurrence continuity: once a trajectory is selected as
    structurally compatible, rollout walks only inside that stored occurrence. It
    never jumps between experiences through a shared address. Compatible paths are
    grouped by their continuation sequence, and the common prefix is exposed until
    the first real divergence. No semantic rules, probabilities or learned weights
    are used.
    """

    def __init__(self, memory: AddressTrajectoryMemory, *, max_depth: int = 3) -> None:
        self.memory = memory
        self.multiscale = MultiscaleAddressResolver(memory, max_depth=max_depth)

    @staticmethod
    def _query_addresses(memory: AddressTrajectoryMemory, text: str) -> tuple[str, ...]:
        tokens = memory._collapse_immediate_tokens(memory.decompose(text))
        return tuple(token.address for token in tokens)

    @staticmethod
    def _matched_positions(trajectory: AddressTrajectory, query: tuple[str, ...]) -> tuple[int, ...]:
        if not query:
            return ()
        query_set = set(query)
        return tuple(index for index, address in enumerate(trajectory.addresses) if address in query_set)

    @classmethod
    def _continuation(
        cls,
        trajectory: AddressTrajectory,
        query: tuple[str, ...],
        *,
        max_steps: int,
    ) -> tuple[tuple[str, ...], tuple[str | None, ...], tuple[str, ...]] | None:
        positions = cls._matched_positions(trajectory, query)
        if not positions:
            return None
        latest = max(positions)
        query_set = set(query)
        addresses: list[str] = []
        surfaces: list[str | None] = []
        for index in range(latest + 1, len(trajectory.addresses)):
            address = trajectory.addresses[index]
            if address in query_set and not addresses:
                continue
            addresses.append(address)
            surfaces.append(trajectory.surfaces[index] if index < len(trajectory.surfaces) else None)
            if len(addresses) >= max_steps:
                break
        matched = tuple(dict.fromkeys(trajectory.addresses[index] for index in positions))
        return tuple(addresses), tuple(surfaces), matched

    @staticmethod
    def _common_prefix(paths: tuple[RolloutPath, ...]) -> tuple[tuple[str, ...], tuple[str | None, ...]]:
        if not paths:
            return (), ()
        min_len = min(len(path.continuation_addresses) for path in paths)
        prefix_len = 0
        for index in range(min_len):
            address = paths[0].continuation_addresses[index]
            if all(path.continuation_addresses[index] == address for path in paths[1:]):
                prefix_len += 1
            else:
                break
        surfaces: list[str | None] = []
        for index in range(prefix_len):
            surface = next(
                (path.continuation_surfaces[index] for path in paths if path.continuation_surfaces[index] is not None),
                None,
            )
            surfaces.append(surface)
        return paths[0].continuation_addresses[:prefix_len], tuple(surfaces)

    def resolve(
        self,
        text: str,
        *,
        max_steps: int = 8,
        candidate_limit: int = 64,
        branch_limit: int = 16,
    ) -> RolloutResolution:
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        query = self._query_addresses(self.memory, text)
        if not query:
            return RolloutResolution(text, (), (), (), None, True)

        matches = self.multiscale.resolve(text, limit=max(candidate_limit, 1))
        by_id = {trajectory.trajectory_id: trajectory for trajectory in self.memory.snapshot()}

        grouped: dict[tuple[str, ...], list[tuple[str, tuple[int, ...], tuple[str, ...], tuple[str | None, ...]]]] = defaultdict(list)
        for match in matches:
            trajectory = by_id.get(match.trajectory_id)
            if trajectory is None:
                continue
            continuation = self._continuation(trajectory, query, max_steps=max_steps)
            if continuation is None:
                continue
            addresses, surfaces, matched = continuation
            if not addresses:
                continue
            grouped[addresses].append((trajectory.trajectory_id, match.supporting_depths, matched, surfaces))

        paths: list[RolloutPath] = []
        for addresses, members in grouped.items():
            trajectory_ids = tuple(sorted({member[0] for member in members}))
            depths = tuple(sorted({depth for member in members for depth in member[1]}))
            matched = tuple(sorted({address for member in members for address in member[2]}))
            surfaces = members[0][3]
            paths.append(
                RolloutPath(
                    trajectory_ids=trajectory_ids,
                    continuation_addresses=addresses,
                    continuation_surfaces=surfaces,
                    supporting_depths=depths,
                    matched_addresses=matched,
                )
            )

        # Only structurally maximal address convergence may open active rollout
        # branches. A weaker occurrence that shares a dense/hub address remains in
        # memory but cannot hitchhike into the current future merely because that
        # address is globally frequent. This preserves occurrence continuity without
        # semantic thresholds or learned scalar weights.
        if paths:
            max_matched = max(len(path.matched_addresses) for path in paths)
            paths = [path for path in paths if len(path.matched_addresses) == max_matched]

        paths.sort(key=lambda item: item.structural_key, reverse=True)
        visible = tuple(paths[: max(0, branch_limit)])
        prefix_addresses, prefix_surfaces = self._common_prefix(visible)
        divergence_index = None
        if len(visible) > 1:
            divergence_index = len(prefix_addresses)
        exhausted = not visible
        return RolloutResolution(
            query=text,
            shared_prefix_addresses=prefix_addresses,
            shared_prefix_surfaces=prefix_surfaces,
            branches=visible,
            divergence_index=divergence_index,
            exhausted=exhausted,
        )
