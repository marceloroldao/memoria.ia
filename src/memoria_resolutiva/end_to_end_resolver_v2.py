from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .address_trajectory_v2 import AddressTrajectoryMemory
from .causal_configuration_signature_v2 import causal_configuration_signature


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
    """End-to-end V2 resolver using only memory + current configuration.

    Precedence is conservative:
    1. exact contiguous frontier evidence;
    2. anonymous *causal* structural fallback;
    3. unresolved.

    The fallback is rebuilt read-only from stored trajectory occurrences. It never
    persists an inferred edge. Prediction deliberately uses a causal structural
    signature that excludes successors/future position from the role fingerprint;
    otherwise a known continuation would leak into the comparison with a frontier
    whose future has not yet been observed.
    """

    def __init__(
        self,
        memory: AddressTrajectoryMemory,
        *,
        enable_structural_fallback: bool = False,
        min_independent_lineages: int = 2,
    ) -> None:
        self.memory = memory
        self.enable_structural_fallback = enable_structural_fallback
        self.min_independent_lineages = min_independent_lineages

    def _direct_futures(self, query_addresses: tuple[str, ...]) -> dict[str, dict[str, object]]:
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
        return futures

    def _structural_futures(self, query_addresses: tuple[str, ...]) -> dict[str, dict[str, object]]:
        query_signature = causal_configuration_signature(
            self.memory,
            query_addresses,
            min_independent_lineages=self.min_independent_lineages,
        )
        if not query_signature.supported or query_signature.signature_id is None:
            return {}

        width = len(query_addresses)
        futures: dict[str, dict[str, object]] = {}
        for trajectory in self.memory.snapshot():
            addresses = trajectory.addresses
            if len(addresses) <= width:
                continue
            for start in range(len(addresses) - width):
                window = tuple(addresses[start:start + width])
                if window == query_addresses:
                    # Exact evidence was already considered by the direct tier.
                    continue
                candidate_signature = causal_configuration_signature(
                    self.memory,
                    window,
                    min_independent_lineages=self.min_independent_lineages,
                )
                if not candidate_signature.supported:
                    continue
                if candidate_signature.signature_id != query_signature.signature_id:
                    continue

                frontier = start + width
                address = addresses[frontier]
                surface = trajectory.surfaces[frontier] if frontier < len(trajectory.surfaces) else None
                bucket = futures.setdefault(address, {"surface": surface, "trajectories": set()})
                trajectories = bucket["trajectories"]
                assert isinstance(trajectories, set)
                trajectories.add(trajectory.trajectory_id)

        # A future inferred structurally must itself have independent occurrence
        # support. This prevents one accidental isomorphism from becoming recall.
        return {
            address: item
            for address, item in futures.items()
            if len(item["trajectories"]) >= self.min_independent_lineages
        }

    @staticmethod
    def _collapse_futures(
        futures: dict[str, dict[str, object]],
        *,
        resolved_source: str,
        conflict_source: str,
    ) -> EndToEndResolution:
        addresses = tuple(sorted(futures))
        if len(addresses) > 1:
            supporting = tuple(sorted({tid for item in futures.values() for tid in item["trajectories"]}))
            return EndToEndResolution(False, True, None, None, conflict_source, addresses, supporting)

        address = addresses[0]
        item = futures[address]
        trajectories = tuple(sorted(item["trajectories"]))
        return EndToEndResolution(True, False, address, item["surface"], resolved_source, addresses, trajectories)

    def resolve_addresses(self, query_addresses: tuple[str, ...]) -> EndToEndResolution:
        if not query_addresses:
            return EndToEndResolution(False, False, None, None, "empty-query")

        direct = self._direct_futures(query_addresses)
        if direct:
            return self._collapse_futures(
                direct,
                resolved_source="direct-contiguous-frontier",
                conflict_source="direct-frontier-conflict",
            )

        if self.enable_structural_fallback:
            structural = self._structural_futures(query_addresses)
            if structural:
                return self._collapse_futures(
                    structural,
                    resolved_source="anonymous-structural-frontier",
                    conflict_source="anonymous-structural-conflict",
                )

        return EndToEndResolution(False, False, None, None, "no-contiguous-frontier")

    def resolve_text(self, text: str) -> EndToEndResolution:
        tokens = self.memory._collapse_immediate_tokens(self.memory.decompose(text))
        return self.resolve_addresses(tuple(token.address for token in tokens))
