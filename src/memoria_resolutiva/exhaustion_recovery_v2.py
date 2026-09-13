from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.dynamic_branch_state_v2 import BranchState, DynamicBranchStateResolver
from memoria_resolutiva.trajectory_rollout_v2 import TrajectoryRolloutResolver, RolloutResolution


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    previous_state: BranchState
    recovered_query_addresses: tuple[str, ...]
    recovery: RolloutResolution
    recovered: bool


class ExhaustionRecoveryResolver:
    """Re-anchor an exhausted dynamic branch state without inventing links.

    Recovery is retrieval-only. The already observed address suffix becomes the new
    structural query seed and is matched against stored occurrence trajectories.
    No edge, fact, trajectory, confidence weight or semantic relation is created.
    The original memory remains immutable.
    """

    def __init__(self, memory: AddressTrajectoryMemory, *, max_depth: int = 3) -> None:
        self.memory = memory
        self.dynamic = DynamicBranchStateResolver(memory, max_depth=max_depth)
        self.rollout = TrajectoryRolloutResolver(memory, max_depth=max_depth)

    @staticmethod
    def _suffixes(addresses: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
        # Prefer the longest observed suffix. Shorter suffixes are fallback anchors
        # only when the longer configuration has no known continuation.
        return tuple(addresses[index:] for index in range(len(addresses)))

    def recover(
        self,
        state: BranchState,
        *,
        max_steps: int = 8,
        candidate_limit: int = 64,
        branch_limit: int = 16,
    ) -> RecoveryResult:
        if not state.exhausted:
            return RecoveryResult(state, (), RolloutResolution("", (), (), (), None, True), False)
        if not state.observed_addresses:
            return RecoveryResult(state, (), RolloutResolution("", (), (), (), None, True), False)

        # Address streams are passed through the same occurrence-trajectory model.
        # Build a temporary textual-free probe only by matching stored addresses;
        # nothing is written to memory.
        snapshot = self.memory.snapshot()
        for suffix in self._suffixes(state.observed_addresses):
            compatible_ids: list[str] = []
            for trajectory in snapshot:
                addresses = trajectory.addresses
                if len(addresses) < len(suffix):
                    continue
                for start in range(0, len(addresses) - len(suffix) + 1):
                    if addresses[start : start + len(suffix)] == suffix:
                        compatible_ids.append(trajectory.trajectory_id)
                        break
            if not compatible_ids:
                continue

            # Convert matching occurrences directly to bounded forward paths while
            # preserving each stored occurrence. No global-graph jumps are allowed.
            from memoria_resolutiva.trajectory_rollout_v2 import RolloutPath
            paths: list[RolloutPath] = []
            for trajectory in snapshot:
                if trajectory.trajectory_id not in compatible_ids:
                    continue
                addresses = trajectory.addresses
                for start in range(0, len(addresses) - len(suffix) + 1):
                    if addresses[start : start + len(suffix)] != suffix:
                        continue
                    cursor = start + len(suffix)
                    continuation_addresses = addresses[cursor : cursor + max_steps]
                    if not continuation_addresses:
                        continue
                    continuation_surfaces = trajectory.surfaces[cursor : cursor + max_steps]
                    paths.append(
                        RolloutPath(
                            trajectory_ids=(trajectory.trajectory_id,),
                            continuation_addresses=continuation_addresses,
                            continuation_surfaces=continuation_surfaces,
                            supporting_depths=(0,),
                            matched_addresses=tuple(dict.fromkeys(suffix)),
                        )
                    )
                    break

            if paths:
                paths.sort(key=lambda item: item.structural_key, reverse=True)
                visible = tuple(paths[: max(0, branch_limit)])
                prefix_addresses, prefix_surfaces = self.rollout._common_prefix(visible)
                result = RolloutResolution(
                    query="",
                    shared_prefix_addresses=prefix_addresses,
                    shared_prefix_surfaces=prefix_surfaces,
                    branches=visible,
                    divergence_index=len(prefix_addresses) if len(visible) > 1 else None,
                    exhausted=False,
                )
                return RecoveryResult(state, suffix, result, True)

        return RecoveryResult(state, (), RolloutResolution("", (), (), (), None, True), False)
