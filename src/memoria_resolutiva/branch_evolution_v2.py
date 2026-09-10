from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.trajectory_rollout_v2 import RolloutPath, TrajectoryRolloutResolver


@dataclass(frozen=True, slots=True)
class EvolvingBranch:
    path: RolloutPath
    cursor: int

    @property
    def remaining_addresses(self) -> tuple[str, ...]:
        return self.path.continuation_addresses[self.cursor :]

    @property
    def remaining_surfaces(self) -> tuple[str | None, ...]:
        return self.path.continuation_surfaces[self.cursor :]


@dataclass(frozen=True, slots=True)
class BranchEvolutionState:
    query: str
    observations: tuple[tuple[str, ...], ...]
    active: tuple[EvolvingBranch, ...]
    eliminated_trajectory_ids: tuple[str, ...]
    collapsed: EvolvingBranch | None
    ambiguous: bool
    exhausted: bool


class BranchEvolutionSession:
    """Narrow rollout branches as new observations arrive.

    Observations never mutate memory and never write truth labels. A branch survives
    only when the new address sequence matches the next contiguous segment of that
    stored occurrence. Shared prefixes keep several branches alive; divergence is
    resolved only when later observations structurally exclude alternatives.
    """

    def __init__(
        self,
        memory: AddressTrajectoryMemory,
        query: str,
        *,
        max_depth: int = 3,
        max_steps: int = 16,
        candidate_limit: int = 64,
        branch_limit: int = 32,
    ) -> None:
        self.memory = memory
        self.query = query
        self._rollout = TrajectoryRolloutResolver(memory, max_depth=max_depth)
        initial = self._rollout.resolve(
            query,
            max_steps=max_steps,
            candidate_limit=candidate_limit,
            branch_limit=branch_limit,
        )
        self._active = tuple(EvolvingBranch(path=path, cursor=0) for path in initial.branches)
        self._observations: list[tuple[str, ...]] = []
        self._eliminated: set[str] = set()

    @staticmethod
    def _advance(branch: EvolvingBranch, observed: tuple[str, ...]) -> EvolvingBranch | None:
        if not observed:
            return branch
        start = branch.cursor
        end = start + len(observed)
        if branch.path.continuation_addresses[start:end] != observed:
            return None
        return EvolvingBranch(path=branch.path, cursor=end)

    def observe_addresses(self, addresses: tuple[str, ...]) -> BranchEvolutionState:
        # Immediate identical-address loops are collapsed consistently with ingest/query.
        collapsed: list[str] = []
        current: str | None = None
        for address in addresses:
            if address == current:
                continue
            collapsed.append(address)
            current = address
        observed = tuple(collapsed)
        if observed:
            self._observations.append(observed)

        survivors: list[EvolvingBranch] = []
        for branch in self._active:
            advanced = self._advance(branch, observed)
            if advanced is None:
                self._eliminated.update(branch.path.trajectory_ids)
            else:
                survivors.append(advanced)
        self._active = tuple(survivors)
        return self.state()

    def observe_text(self, text: str) -> BranchEvolutionState:
        tokens = self.memory._collapse_immediate_tokens(self.memory.decompose(text))
        return self.observe_addresses(tuple(token.address for token in tokens))

    def state(self) -> BranchEvolutionState:
        active = self._active
        exhausted = len(active) == 0
        collapsed = active[0] if len(active) == 1 else None
        ambiguous = len(active) > 1
        return BranchEvolutionState(
            query=self.query,
            observations=tuple(self._observations),
            active=active,
            eliminated_trajectory_ids=tuple(sorted(self._eliminated)),
            collapsed=collapsed,
            ambiguous=ambiguous,
            exhausted=exhausted,
        )
