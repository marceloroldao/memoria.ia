from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .address_trajectory_v2 import AddressTrajectoryMemory


@dataclass(frozen=True, slots=True)
class EndToEndResolution:
    resolved: bool
    ambiguous: bool
    address: str | None
    surface: str | None
    source: str
    competing_addresses: tuple[str, ...] = ()
    supporting_trajectories: tuple[str, ...] = ()


def _find_contiguous(haystack: Sequence[str], needle: Sequence[str]) -> tuple[int, ...]:
    if not needle or len(needle) > len(haystack):
        return ()
    width = len(needle)
    return tuple(
        i for i in range(len(haystack) - width + 1)
        if tuple(haystack[i:i + width]) == tuple(needle)
    )


class EndToEndAddressResolver:
    """First end-to-end V2 resolver using only memory + current configuration.

    The caller supplies no semantic schema, relation profile, candidate list or
    learned weight. Resolution is occurrence-preserving: after a contiguous match,
    the next address is read from that same trajectory occurrence. Different
    occurrences may support competing futures; ties remain ambiguous.
    """

    def __init__(self, memory: AddressTrajectoryMemory) -> None:
        self.memory = memory

    def resolve_addresses(self, query_addresses: tuple[str, ...]) -> EndToEndResolution:
        if not query_addresses:
            return EndToEndResolution(False, False, None, None, "empty-query")

        futures: dict[str, dict[str, object]] = {}
        for trajectory in self.memory.snapshot():
            for start in _find_contiguous(trajectory.addresses, query_addresses):
                frontier = start + len(query_addresses)
                if frontier >= len(trajectory.addresses):
                    continue
                address = trajectory.addresses[frontier]
                surface = trajectory.surfaces[frontier] if frontier < len(trajectory.surfaces) else None
                bucket = futures.setdefault(address, {"surface": surface, "trajectories": set()})
                trajectories = bucket["trajectories"]
                assert isinstance(trajectories, set)
                trajectories.add(trajectory.trajectory_id)

        if not futures:
            return EndToEndResolution(False, False, None, None, "no-contiguous-frontier")

        addresses = tuple(sorted(futures))
        if len(addresses) > 1:
            supporting = tuple(sorted({tid for item in futures.values() for tid in item["trajectories"]}))
            return EndToEndResolution(False, True, None, None, "direct-frontier-conflict", addresses, supporting)

        address = addresses[0]
        item = futures[address]
        trajectories = tuple(sorted(item["trajectories"]))
        return EndToEndResolution(True, False, address, item["surface"], "direct-contiguous-frontier", addresses, trajectories)

    def resolve_text(self, text: str) -> EndToEndResolution:
        tokens = self.memory._collapse_immediate_tokens(self.memory.decompose(text))
        return self.resolve_addresses(tuple(token.address for token in tokens))
