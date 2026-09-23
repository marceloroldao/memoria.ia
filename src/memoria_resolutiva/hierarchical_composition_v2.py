from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import blake2b
import json
from typing import TypeAlias

from .structural_trajectory_v2 import StructuralTrajectoryIndex


ScaleAddress: TypeAlias = int | str


def _composition_address(
    *,
    hierarchy_id: str,
    depth: int,
    children: tuple[ScaleAddress, ...],
) -> str:
    payload = {
        "schema": "memoria.ia-hierarchical-composition-v3",
        "hierarchy_id": hierarchy_id,
        "depth": int(depth),
        "children": [
            {"kind": "atomic" if isinstance(child, int) else "composed", "value": child}
            for child in children
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "hc3:" + blake2b(encoded, digest_size=20).hexdigest()


@dataclass(frozen=True, slots=True)
class HierarchicalCompositionV2:
    address: str
    hierarchy_id: str
    children: tuple[ScaleAddress, ...]
    depth: int
    occurrences: int
    trajectory_count: int
    first_seen_order: int


@dataclass(frozen=True, slots=True)
class HierarchyLevelV2:
    hierarchy_id: str
    depth: int
    compositions: tuple[HierarchicalCompositionV2, ...]
    transformed_trajectories: tuple[tuple[str, tuple[ScaleAddress, ...]], ...]


class HierarchicalCompositionEngineV2:
    """Derive recurrent structural compositions without semantic labels.

    Atomic trajectories are never mutated. A composition is promoted only when
    its contiguous child sequence recurs with the configured support, including
    support from multiple distinct trajectory occurrences by default.
    """

    def __init__(
        self,
        trajectories: StructuralTrajectoryIndex,
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
        if min_trajectory_count < 2:
            raise ValueError("min_trajectory_count must be >= 2")
        if min_size < 2 or max_size < min_size:
            raise ValueError("invalid composition size range")
        if max_compositions_per_level < 1:
            raise ValueError("max_compositions_per_level must be >= 1")
        self.trajectories = trajectories
        self.max_depth = max_depth
        self.min_occurrences = min_occurrences
        self.min_trajectory_count = min_trajectory_count
        self.min_size = min_size
        self.max_size = max_size
        self.max_compositions_per_level = max_compositions_per_level

    @staticmethod
    def collapse_with_catalogue(
        addresses: tuple[ScaleAddress, ...],
        catalogue: tuple[HierarchicalCompositionV2, ...],
    ) -> tuple[ScaleAddress, ...]:
        by_first: dict[ScaleAddress, list[HierarchicalCompositionV2]] = defaultdict(list)
        for composition in catalogue:
            if not composition.children:
                continue
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

        output: list[ScaleAddress] = []
        cursor = 0
        while cursor < len(addresses):
            selected: HierarchicalCompositionV2 | None = None
            for candidate in by_first.get(addresses[cursor], ()):
                width = len(candidate.children)
                if addresses[cursor : cursor + width] == candidate.children:
                    selected = candidate
                    break
            if selected is None:
                output.append(addresses[cursor])
                cursor += 1
            else:
                output.append(selected.address)
                cursor += len(selected.children)
        return tuple(output)

    def _atomic_streams(
        self,
        hierarchy_id: str,
    ) -> tuple[tuple[str, tuple[ScaleAddress, ...]], ...]:
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        return tuple(
            (trajectory.trajectory_id, tuple(trajectory.addresses))
            for trajectory in self.trajectories.snapshot()
            if trajectory.hierarchy_id == hierarchy
        )

    def _discover_level(
        self,
        streams: tuple[tuple[str, tuple[ScaleAddress, ...]], ...],
        *,
        hierarchy_id: str,
        depth: int,
    ) -> tuple[HierarchicalCompositionV2, ...]:
        counts: dict[tuple[ScaleAddress, ...], int] = defaultdict(int)
        supporting_trajectories: dict[tuple[ScaleAddress, ...], set[str]] = defaultdict(set)
        first_seen: dict[tuple[ScaleAddress, ...], int] = {}
        order = 0

        for trajectory_id, addresses in streams:
            for size in range(self.min_size, self.max_size + 1):
                if len(addresses) < size:
                    continue
                for start in range(len(addresses) - size + 1):
                    children = addresses[start : start + size]
                    counts[children] += 1
                    supporting_trajectories[children].add(trajectory_id)
                    if children not in first_seen:
                        first_seen[children] = order
                        order += 1

        candidates: list[HierarchicalCompositionV2] = []
        seen_addresses: dict[str, tuple[ScaleAddress, ...]] = {}
        for children, occurrences in counts.items():
            trajectory_count = len(supporting_trajectories[children])
            if occurrences < self.min_occurrences:
                continue
            if trajectory_count < self.min_trajectory_count:
                continue
            address = _composition_address(
                hierarchy_id=hierarchy_id,
                depth=depth,
                children=children,
            )
            previous = seen_addresses.get(address)
            if previous is not None and previous != children:
                raise ValueError("hierarchical composition address collision")
            seen_addresses[address] = children
            candidates.append(
                HierarchicalCompositionV2(
                    address=address,
                    hierarchy_id=hierarchy_id,
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

    def build(self, *, hierarchy_id: str) -> tuple[HierarchyLevelV2, ...]:
        hierarchy = str(hierarchy_id).strip()
        streams = self._atomic_streams(hierarchy)
        levels: list[HierarchyLevelV2] = []

        for depth in range(1, self.max_depth + 1):
            catalogue = self._discover_level(
                streams,
                hierarchy_id=hierarchy,
                depth=depth,
            )
            if not catalogue:
                break
            transformed = tuple(
                (
                    trajectory_id,
                    self.collapse_with_catalogue(addresses, catalogue),
                )
                for trajectory_id, addresses in streams
            )
            levels.append(
                HierarchyLevelV2(
                    hierarchy_id=hierarchy,
                    depth=depth,
                    compositions=catalogue,
                    transformed_trajectories=transformed,
                )
            )
            if transformed == streams:
                break
            streams = transformed

        return tuple(levels)

    def transform_addresses(
        self,
        addresses: tuple[int, ...],
        *,
        hierarchy_id: str,
    ) -> tuple[ScaleAddress, ...]:
        output: tuple[ScaleAddress, ...] = tuple(addresses)
        for level in self.build(hierarchy_id=hierarchy_id):
            output = self.collapse_with_catalogue(output, level.compositions)
        return output

    def metrics(self, *, hierarchy_id: str) -> dict[str, object]:
        atomic_streams = self._atomic_streams(hierarchy_id)
        levels = self.build(hierarchy_id=hierarchy_id)
        atomic_count = sum(len(addresses) for _, addresses in atomic_streams)
        if levels:
            final_count = sum(
                len(addresses)
                for _, addresses in levels[-1].transformed_trajectories
            )
        else:
            final_count = atomic_count
        return {
            "hierarchy_id": hierarchy_id,
            "levels": len(levels),
            "compositions_per_level": [
                len(level.compositions)
                for level in levels
            ],
            "atomic_address_count": atomic_count,
            "final_address_count": final_count,
            "compression_num": atomic_count - final_count,
            "compression_den": max(1, atomic_count),
            "semantic_projection": False,
        }
