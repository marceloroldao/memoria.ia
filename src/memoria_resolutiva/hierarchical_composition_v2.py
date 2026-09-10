from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from collections import defaultdict

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory


def _hier_address(children: tuple[str, ...], depth: int) -> str:
    payload = f"memoria.hierarchical-composition.v2\x00{depth}\x00" + "\x1f".join(children)
    return "hc2:" + blake2b(payload.encode("utf-8"), digest_size=16).hexdigest()


@dataclass(frozen=True, slots=True)
class HierarchicalComposition:
    address: str
    children: tuple[str, ...]
    depth: int
    occurrences: int
    trajectory_count: int
    first_seen_order: int


@dataclass(frozen=True, slots=True)
class HierarchyLevel:
    depth: int
    compositions: tuple[HierarchicalComposition, ...]
    transformed_trajectories: tuple[tuple[str, tuple[str, ...]], ...]


class HierarchicalCompositionEngine:
    """Build recurrent compositions of recurrent compositions without semantics.

    Each level is derived from the previous level's address streams. Promotion is
    allowed only when a contiguous pattern recurs often enough. Original atomic
    trajectories remain untouched in AddressTrajectoryMemory.
    """

    def __init__(
        self,
        memory: AddressTrajectoryMemory,
        *,
        max_depth: int = 3,
        min_occurrences: int = 2,
        min_trajectory_count: int = 2,
        min_size: int = 2,
        max_size: int = 3,
        max_compositions_per_level: int = 2048,
    ) -> None:
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        if min_occurrences < 2:
            raise ValueError("min_occurrences must be >= 2")
        if min_trajectory_count < 1:
            raise ValueError("min_trajectory_count must be >= 1")
        if min_size < 2 or max_size < min_size:
            raise ValueError("invalid composition size range")
        if max_compositions_per_level < 1:
            raise ValueError("max_compositions_per_level must be >= 1")
        self.memory = memory
        self.max_depth = max_depth
        self.min_occurrences = min_occurrences
        self.min_trajectory_count = min_trajectory_count
        self.min_size = min_size
        self.max_size = max_size
        self.max_compositions_per_level = max_compositions_per_level

    @staticmethod
    def _collapse_with_catalogue(
        addresses: tuple[str, ...],
        catalogue: tuple[HierarchicalComposition, ...],
    ) -> tuple[str, ...]:
        by_first: dict[str, list[HierarchicalComposition]] = defaultdict(list)
        for composition in catalogue:
            by_first[composition.children[0]].append(composition)
        for candidates in by_first.values():
            candidates.sort(
                key=lambda item: (
                    len(item.children),
                    item.trajectory_count,
                    item.occurrences,
                    item.address,
                ),
                reverse=True,
            )

        output: list[str] = []
        cursor = 0
        while cursor < len(addresses):
            selected: HierarchicalComposition | None = None
            for candidate in by_first.get(addresses[cursor], ()):
                size = len(candidate.children)
                if addresses[cursor : cursor + size] == candidate.children:
                    selected = candidate
                    break
            if selected is None:
                output.append(addresses[cursor])
                cursor += 1
            else:
                output.append(selected.address)
                cursor += len(selected.children)
        return tuple(output)

    def _discover_level(
        self,
        streams: tuple[tuple[str, tuple[str, ...]], ...],
        depth: int,
    ) -> tuple[HierarchicalComposition, ...]:
        counts: dict[tuple[str, ...], int] = defaultdict(int)
        trajectories: dict[tuple[str, ...], set[str]] = defaultdict(set)
        first_seen: dict[tuple[str, ...], int] = {}
        order = 0

        for trajectory_id, addresses in streams:
            for size in range(self.min_size, self.max_size + 1):
                if len(addresses) < size:
                    continue
                for start in range(len(addresses) - size + 1):
                    children = addresses[start : start + size]
                    counts[children] += 1
                    trajectories[children].add(trajectory_id)
                    if children not in first_seen:
                        first_seen[children] = order
                        order += 1

        candidates: list[HierarchicalComposition] = []
        for children, occurrences in counts.items():
            trajectory_count = len(trajectories[children])
            if occurrences < self.min_occurrences:
                continue
            if trajectory_count < self.min_trajectory_count:
                continue
            candidates.append(
                HierarchicalComposition(
                    address=_hier_address(children, depth),
                    children=children,
                    depth=depth,
                    occurrences=occurrences,
                    trajectory_count=trajectory_count,
                    first_seen_order=first_seen[children],
                )
            )

        candidates.sort(
            key=lambda item: (
                item.trajectory_count,
                item.occurrences,
                len(item.children),
                -item.first_seen_order,
                item.address,
            ),
            reverse=True,
        )
        return tuple(candidates[: self.max_compositions_per_level])

    def build(self) -> tuple[HierarchyLevel, ...]:
        streams = tuple(
            (trajectory.trajectory_id, trajectory.addresses)
            for trajectory in self.memory.snapshot()
        )
        levels: list[HierarchyLevel] = []

        for depth in range(1, self.max_depth + 1):
            catalogue = self._discover_level(streams, depth)
            if not catalogue:
                break
            transformed = tuple(
                (trajectory_id, self._collapse_with_catalogue(addresses, catalogue))
                for trajectory_id, addresses in streams
            )
            levels.append(
                HierarchyLevel(
                    depth=depth,
                    compositions=catalogue,
                    transformed_trajectories=transformed,
                )
            )
            if transformed == streams:
                break
            streams = transformed

        return tuple(levels)

    def transform_addresses(self, addresses: tuple[str, ...]) -> tuple[str, ...]:
        output = addresses
        for level in self.build():
            output = self._collapse_with_catalogue(output, level.compositions)
        return output

    def transform_text(self, text: str) -> tuple[str, ...]:
        tokens = self.memory._collapse_immediate_tokens(self.memory.decompose(text))
        return self.transform_addresses(tuple(token.address for token in tokens))

    def metrics(self) -> dict[str, object]:
        levels = self.build()
        atomic_count = sum(len(t.addresses) for t in self.memory.snapshot())
        if levels:
            final_count = sum(len(addresses) for _, addresses in levels[-1].transformed_trajectories)
        else:
            final_count = atomic_count
        return {
            "levels": len(levels),
            "compositions_per_level": [len(level.compositions) for level in levels],
            "atomic_address_count": atomic_count,
            "final_address_count": final_count,
            "compression_num": atomic_count - final_count,
            "compression_den": max(atomic_count, 1),
        }
