from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.trajectory_rollout_v2 import RolloutPath, TrajectoryRolloutResolver


@dataclass(frozen=True, slots=True)
class ActiveBranch:
    trajectory_ids: tuple[str, ...]
    remaining_addresses: tuple[str, ...]
    remaining_surfaces: tuple[str | None, ...]
    supporting_depths: tuple[int, ...]
    matched_addresses: tuple[str, ...]
    consumed_steps: int

    @property
    def structural_key(self) -> tuple[int, int, int, int, tuple[str, ...]]:
        return (
            len(self.supporting_depths),
            len(self.trajectory_ids),
            len(self.matched_addresses),
            -self.consumed_steps,
            self.remaining_addresses,
        )


@dataclass(frozen=True, slots=True)
class BranchState:
    query: str
    observed_addresses: tuple[str, ...]
    active: tuple[ActiveBranch, ...]
    eliminated_trajectory_ids: tuple[str, ...]
    exhausted: bool
    ambiguous: bool


class DynamicBranchStateResolver:
    """Update rollout hypotheses with new observations without creating facts.

    A branch survives only when incoming observed addresses match its next expected
    continuation addresses in order. Branches that no longer fit are eliminated from
    the active hypothesis set, but the underlying stored trajectories are never
    deleted or marked false. The state is therefore an ephemeral structural view.
    """

    def __init__(self, memory: AddressTrajectoryMemory, *, max_depth: int = 3) -> None:
        self.memory = memory
        self.rollout = TrajectoryRolloutResolver(memory, max_depth=max_depth)

    @staticmethod
    def _from_path(path: RolloutPath) -> ActiveBranch:
        return ActiveBranch(
            trajectory_ids=path.trajectory_ids,
            remaining_addresses=path.continuation_addresses,
            remaining_surfaces=path.continuation_surfaces,
            supporting_depths=path.supporting_depths,
            matched_addresses=path.matched_addresses,
            consumed_steps=0,
        )

    def begin(
        self,
        text: str,
        *,
        max_steps: int = 8,
        candidate_limit: int = 64,
        branch_limit: int = 16,
    ) -> BranchState:
        resolution = self.rollout.resolve(
            text,
            max_steps=max_steps,
            candidate_limit=candidate_limit,
            branch_limit=branch_limit,
        )
        active = tuple(sorted((self._from_path(path) for path in resolution.branches), key=lambda item: item.structural_key, reverse=True))
        return BranchState(
            query=text,
            observed_addresses=(),
            active=active,
            eliminated_trajectory_ids=(),
            exhausted=not active,
            ambiguous=len(active) > 1,
        )

    @staticmethod
    def observe_address(state: BranchState, address: str) -> BranchState:
        if not address:
            raise ValueError("address must be non-empty")
        survivors: list[ActiveBranch] = []
        eliminated: set[str] = set(state.eliminated_trajectory_ids)

        for branch in state.active:
            if not branch.remaining_addresses:
                eliminated.update(branch.trajectory_ids)
                continue
            if branch.remaining_addresses[0] != address:
                eliminated.update(branch.trajectory_ids)
                continue
            survivors.append(
                ActiveBranch(
                    trajectory_ids=branch.trajectory_ids,
                    remaining_addresses=branch.remaining_addresses[1:],
                    remaining_surfaces=branch.remaining_surfaces[1:],
                    supporting_depths=branch.supporting_depths,
                    matched_addresses=branch.matched_addresses,
                    consumed_steps=branch.consumed_steps + 1,
                )
            )

        survivors.sort(key=lambda item: item.structural_key, reverse=True)
        return BranchState(
            query=state.query,
            observed_addresses=state.observed_addresses + (address,),
            active=tuple(survivors),
            eliminated_trajectory_ids=tuple(sorted(eliminated)),
            exhausted=not survivors,
            ambiguous=len(survivors) > 1,
        )

    def observe_text(self, state: BranchState, text: str) -> BranchState:
        tokens = self.memory._collapse_immediate_tokens(self.memory.decompose(text))
        current = state
        for token in tokens:
            current = self.observe_address(current, token.address)
            if current.exhausted:
                break
        return current
