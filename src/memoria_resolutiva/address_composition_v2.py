from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from collections import defaultdict

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory


def _composition_address(children: tuple[str, ...]) -> str:
    payload = "memoria.address-composition.v2\x00" + "\x1f".join(children)
    return "ac2:" + blake2b(payload.encode("utf-8"), digest_size=16).hexdigest()


@dataclass(frozen=True, slots=True)
class AddressComposition:
    address: str
    children: tuple[str, ...]
    occurrences: int
    trajectory_count: int
    first_seen_order: int


class AddressCompositionEngine:
    """Discover reusable contiguous address compositions without semantics.

    A composition is promoted only because the same contiguous address sequence
    recurs in observed trajectories. No token meaning, language rule, embedding,
    learned weight or intent class participates in discovery.
    """

    def __init__(
        self,
        memory: AddressTrajectoryMemory,
        *,
        min_size: int = 2,
        max_size: int = 4,
        min_occurrences: int = 2,
    ) -> None:
        if min_size < 2:
            raise ValueError("min_size must be >= 2")
        if max_size < min_size:
            raise ValueError("max_size must be >= min_size")
        if min_occurrences < 2:
            raise ValueError("min_occurrences must be >= 2")
        self.memory = memory
        self.min_size = min_size
        self.max_size = max_size
        self.min_occurrences = min_occurrences

    def discover(self) -> tuple[AddressComposition, ...]:
        counts: dict[tuple[str, ...], int] = defaultdict(int)
        trajectories: dict[tuple[str, ...], set[str]] = defaultdict(set)
        first_seen: dict[tuple[str, ...], int] = {}
        order = 0

        for trajectory in self.memory.snapshot():
            addresses = trajectory.addresses
            for size in range(self.min_size, self.max_size + 1):
                if len(addresses) < size:
                    continue
                for start in range(0, len(addresses) - size + 1):
                    children = addresses[start : start + size]
                    counts[children] += 1
                    trajectories[children].add(trajectory.trajectory_id)
                    if children not in first_seen:
                        first_seen[children] = order
                        order += 1

        result: list[AddressComposition] = []
        for children, occurrences in counts.items():
            if occurrences < self.min_occurrences:
                continue
            result.append(
                AddressComposition(
                    address=_composition_address(children),
                    children=children,
                    occurrences=occurrences,
                    trajectory_count=len(trajectories[children]),
                    first_seen_order=first_seen[children],
                )
            )

        result.sort(
            key=lambda item: (
                item.trajectory_count,
                item.occurrences,
                len(item.children),
                -item.first_seen_order,
                item.address,
            ),
            reverse=True,
        )
        return tuple(result)

    def compose_addresses(
        self,
        addresses: tuple[str, ...],
        *,
        catalogue: tuple[AddressComposition, ...] | None = None,
    ) -> tuple[str, ...]:
        """Collapse known compositions using deterministic longest-first matching.

        This is a structural transform only. The original trajectory remains
        preserved in AddressTrajectoryMemory; composition creates a derived view.
        """
        if catalogue is None:
            catalogue = self.discover()
        by_first: dict[str, list[AddressComposition]] = defaultdict(list)
        for composition in catalogue:
            by_first[composition.children[0]].append(composition)
        for candidates in by_first.values():
            candidates.sort(
                key=lambda item: (len(item.children), item.trajectory_count, item.occurrences, item.address),
                reverse=True,
            )

        output: list[str] = []
        cursor = 0
        while cursor < len(addresses):
            selected: AddressComposition | None = None
            for candidate in by_first.get(addresses[cursor], ()):  # longest-first
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

    def compose_text(self, text: str) -> tuple[str, ...]:
        tokens = self.memory._collapse_immediate_tokens(self.memory.decompose(text))
        addresses = tuple(token.address for token in tokens)
        return self.compose_addresses(addresses)
