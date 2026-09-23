from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .structural_rollout_v2 import (
    StructuralRolloutPathV2,
    StructuralRolloutResolverV2,
    StructuralRolloutWitnessV2,
)
from .structural_trajectory_v2 import StructuralTrajectory, StructuralTrajectoryIndex


@dataclass(frozen=True, slots=True)
class ActiveStructuralBranchV2:
    witnesses: tuple[StructuralRolloutWitnessV2, ...]
    trajectory_ids: tuple[str, ...]
    remaining_addresses: tuple[int, ...]
    supporting_depths: tuple[int, ...]
    matched_addresses: tuple[int, ...]
    consumed_steps: int

    @property
    def terminal(self) -> bool:
        return not self.remaining_addresses


@dataclass(frozen=True, slots=True)
class StructuralBranchStateV2:
    hierarchy_id: str
    seed_addresses: tuple[int, ...]
    observed_addresses: tuple[int, ...]
    active: tuple[ActiveStructuralBranchV2, ...]
    terminal_trajectory_ids: tuple[str, ...]
    eliminated_trajectory_ids: tuple[str, ...]
    exhausted: bool
    ambiguous: bool
    terminal: bool
    bounded_out: bool
    reason: str


@dataclass(frozen=True, slots=True)
class StructuralBranchRecoveryV2:
    previous: StructuralBranchStateV2
    observation_addresses: tuple[int, ...]
    recovered: StructuralBranchStateV2
    recovered_any: bool
    matched_suffix: tuple[int, ...]


class DynamicStructuralBranchResolverV2:
    """Narrow structural rollout branches using new observed addresses.

    Branch state is ephemeral. Eliminating a branch never deletes or weakens the
    underlying stored occurrence. Repeated adjacent observations do not consume
    multiple expected steps. Terminal occurrences remain explicit competing
    hypotheses until a later observation rules them out.
    """

    def __init__(
        self,
        trajectories: StructuralTrajectoryIndex,
        *,
        max_depth: int = 3,
    ) -> None:
        self.trajectories = trajectories
        self.rollout = StructuralRolloutResolverV2(
            trajectories,
            max_depth=max_depth,
        )

    @staticmethod
    def _collapse(addresses) -> tuple[int, ...]:
        out: list[int] = []
        current: int | None = None
        for raw in addresses:
            value = int(raw)
            if value < 0:
                raise ValueError("structural addresses must be >= 0")
            if current == value:
                continue
            out.append(value)
            current = value
        return tuple(out)

    @staticmethod
    def _from_path(path: StructuralRolloutPathV2) -> ActiveStructuralBranchV2:
        return ActiveStructuralBranchV2(
            witnesses=path.witnesses,
            trajectory_ids=path.trajectory_ids,
            remaining_addresses=path.continuation_addresses,
            supporting_depths=path.supporting_depths,
            matched_addresses=path.matched_addresses,
            consumed_steps=0,
        )

    def begin_addresses(
        self,
        addresses,
        *,
        hierarchy_id: str,
        max_steps: int = 8,
        candidate_limit: int = 64,
        branch_limit: int = 16,
    ) -> StructuralBranchStateV2:
        seed = self._collapse(addresses)
        rollout = self.rollout.resolve_addresses(
            seed,
            hierarchy_id=hierarchy_id,
            max_steps=max_steps,
            candidate_limit=candidate_limit,
            branch_limit=branch_limit,
        )
        active = tuple(self._from_path(path) for path in rollout.branches)
        terminals = rollout.terminal_trajectory_ids
        outcome_count = len(active) + (1 if terminals else 0)
        return StructuralBranchStateV2(
            hierarchy_id=hierarchy_id,
            seed_addresses=seed,
            observed_addresses=(),
            active=active,
            terminal_trajectory_ids=terminals,
            eliminated_trajectory_ids=(),
            exhausted=rollout.exhausted,
            ambiguous=outcome_count > 1,
            terminal=bool(terminals) and not active,
            bounded_out=rollout.bounded_out,
            reason=rollout.reason,
        )

    @staticmethod
    def observe_address(
        state: StructuralBranchStateV2,
        address: int,
    ) -> StructuralBranchStateV2:
        value = int(address)
        if value < 0:
            raise ValueError("structural address must be >= 0")
        if state.observed_addresses and state.observed_addresses[-1] == value:
            return state
        if state.exhausted:
            return state

        survivors: list[ActiveStructuralBranchV2] = []
        eliminated: set[str] = set(state.eliminated_trajectory_ids)
        # Any new observed address rules out hypotheses that had already ended.
        eliminated.update(state.terminal_trajectory_ids)

        for branch in state.active:
            if not branch.remaining_addresses:
                eliminated.update(branch.trajectory_ids)
                continue
            if branch.remaining_addresses[0] != value:
                eliminated.update(branch.trajectory_ids)
                continue
            survivors.append(
                ActiveStructuralBranchV2(
                    witnesses=branch.witnesses,
                    trajectory_ids=branch.trajectory_ids,
                    remaining_addresses=branch.remaining_addresses[1:],
                    supporting_depths=branch.supporting_depths,
                    matched_addresses=branch.matched_addresses,
                    consumed_steps=branch.consumed_steps + 1,
                )
            )

        active = tuple(survivors)
        exhausted = not active
        return StructuralBranchStateV2(
            hierarchy_id=state.hierarchy_id,
            seed_addresses=state.seed_addresses,
            observed_addresses=state.observed_addresses + (value,),
            active=active,
            terminal_trajectory_ids=(),
            eliminated_trajectory_ids=tuple(sorted(eliminated)),
            exhausted=exhausted,
            ambiguous=len(active) > 1,
            terminal=bool(active) and all(item.terminal for item in active),
            bounded_out=False,
            reason=(
                "observation-exhausted-branches"
                if exhausted
                else "single-active-branch"
                if len(active) == 1
                else "competing-active-branches"
            ),
        )

    def observe_addresses(
        self,
        state: StructuralBranchStateV2,
        addresses,
    ) -> StructuralBranchStateV2:
        current = state
        values = self._collapse(addresses)
        if (
            current.observed_addresses
            and values
            and current.observed_addresses[-1] == values[0]
        ):
            values = values[1:]
        for value in values:
            current = self.observe_address(current, value)
            if current.exhausted:
                break
        return current

    @staticmethod
    def _exact_occurrences(
        candidate: tuple[int, ...],
        suffix: tuple[int, ...],
    ) -> tuple[int, ...]:
        if not suffix or len(candidate) < len(suffix):
            return ()
        width = len(suffix)
        return tuple(
            start
            for start in range(len(candidate) - width + 1)
            if candidate[start : start + width] == suffix
        )

    @staticmethod
    def _empty_state(
        hierarchy_id: str,
        seed: tuple[int, ...],
        *,
        reason: str,
        bounded_out: bool = False,
        terminal_trajectory_ids: tuple[str, ...] = (),
        terminal: bool = False,
    ) -> StructuralBranchStateV2:
        return StructuralBranchStateV2(
            hierarchy_id=hierarchy_id,
            seed_addresses=seed,
            observed_addresses=(),
            active=(),
            terminal_trajectory_ids=terminal_trajectory_ids,
            eliminated_trajectory_ids=(),
            exhausted=True,
            ambiguous=False,
            terminal=terminal,
            bounded_out=bounded_out,
            reason=reason,
        )

    def _recover_suffix(
        self,
        observation: tuple[int, ...],
        *,
        hierarchy_id: str,
        max_steps: int,
        candidate_limit: int,
        branch_limit: int,
    ) -> tuple[StructuralBranchStateV2, tuple[int, ...]]:
        if not observation:
            return (
                self._empty_state(
                    hierarchy_id,
                    (),
                    reason="empty-recovery-observation",
                ),
                (),
            )

        snapshot = tuple(
            item
            for item in self.trajectories.snapshot()
            if item.hierarchy_id == hierarchy_id
        )

        for start_suffix in range(len(observation)):
            suffix = observation[start_suffix:]
            exact_witnesses: list[tuple[StructuralTrajectory, int]] = []
            for trajectory in snapshot:
                for start in self._exact_occurrences(trajectory.addresses, suffix):
                    exact_witnesses.append((trajectory, start))

            if not exact_witnesses:
                continue

            if len(exact_witnesses) > candidate_limit:
                return (
                    self._empty_state(
                        hierarchy_id,
                        suffix,
                        reason="recovery-limit-exceeded",
                        bounded_out=True,
                    ),
                    suffix,
                )

            grouped: dict[
                tuple[int, ...],
                list[StructuralRolloutWitnessV2],
            ] = defaultdict(list)
            terminal_ids: set[str] = set()

            for trajectory, start in exact_witnesses:
                cursor = start + len(suffix)
                continuation = trajectory.addresses[cursor : cursor + max_steps]
                if not continuation:
                    terminal_ids.add(trajectory.trajectory_id)
                    continue
                grouped[continuation].append(
                    StructuralRolloutWitnessV2(
                        trajectory_id=trajectory.trajectory_id,
                        anchor_index=cursor - 1,
                    )
                )

            outcome_count = len(grouped) + (1 if terminal_ids else 0)
            if outcome_count > branch_limit:
                return (
                    self._empty_state(
                        hierarchy_id,
                        suffix,
                        reason="recovery-limit-exceeded",
                        bounded_out=True,
                    ),
                    suffix,
                )

            # A known full suffix that only reaches terminal occurrences must stop.
            # Do not shorten it and stitch through a hub in another occurrence.
            if not grouped:
                terminals = tuple(sorted(terminal_ids))
                return (
                    self._empty_state(
                        hierarchy_id,
                        suffix,
                        reason="recovery-matched-terminal",
                        terminal_trajectory_ids=terminals,
                        terminal=True,
                    ),
                    suffix,
                )

            active: list[ActiveStructuralBranchV2] = []
            for continuation, witnesses_raw in grouped.items():
                witnesses = tuple(
                    sorted(
                        set(witnesses_raw),
                        key=lambda item: (item.trajectory_id, item.anchor_index),
                    )
                )
                active.append(
                    ActiveStructuralBranchV2(
                        witnesses=witnesses,
                        trajectory_ids=tuple(sorted({w.trajectory_id for w in witnesses})),
                        remaining_addresses=continuation,
                        supporting_depths=(0,),
                        matched_addresses=tuple(dict.fromkeys(suffix)),
                        consumed_steps=0,
                    )
                )

            active.sort(key=lambda item: (item.remaining_addresses, item.trajectory_ids))
            visible = tuple(active)
            terminals = tuple(sorted(terminal_ids))
            ambiguous = len(visible) + (1 if terminals else 0) > 1
            return (
                StructuralBranchStateV2(
                    hierarchy_id=hierarchy_id,
                    seed_addresses=suffix,
                    observed_addresses=(),
                    active=visible,
                    terminal_trajectory_ids=terminals,
                    eliminated_trajectory_ids=(),
                    exhausted=False,
                    ambiguous=ambiguous,
                    terminal=False,
                    bounded_out=False,
                    reason=(
                        "recovered-competing-outcomes"
                        if ambiguous
                        else "recovered-single-branch"
                    ),
                ),
                suffix,
            )

        return (
            self._empty_state(
                hierarchy_id,
                observation,
                reason="recovery-no-occurrence",
            ),
            (),
        )

    def recover_addresses(
        self,
        state: StructuralBranchStateV2,
        addresses,
        *,
        max_steps: int = 8,
        candidate_limit: int = 64,
        branch_limit: int = 16,
    ) -> StructuralBranchRecoveryV2:
        if not state.exhausted:
            raise ValueError("recovery requires an exhausted branch state")
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if candidate_limit < 1:
            raise ValueError("candidate_limit must be >= 1")
        if branch_limit < 1:
            raise ValueError("branch_limit must be >= 1")
        observation = self._collapse(addresses)
        recovered, suffix = self._recover_suffix(
            observation,
            hierarchy_id=state.hierarchy_id,
            max_steps=max_steps,
            candidate_limit=candidate_limit,
            branch_limit=branch_limit,
        )
        return StructuralBranchRecoveryV2(
            previous=state,
            observation_addresses=observation,
            recovered=recovered,
            recovered_any=not recovered.exhausted,
            matched_suffix=suffix,
        )
