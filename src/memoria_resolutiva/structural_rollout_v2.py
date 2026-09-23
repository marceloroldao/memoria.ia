from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .multiscale_resolver_v2 import MultiscaleStructuralResolverV2
from .structural_trajectory_v2 import StructuralTrajectory, StructuralTrajectoryIndex


@dataclass(frozen=True, slots=True)
class StructuralRolloutWitnessV2:
    trajectory_id: str
    anchor_index: int


@dataclass(frozen=True, slots=True)
class StructuralRolloutPathV2:
    witnesses: tuple[StructuralRolloutWitnessV2, ...]
    trajectory_ids: tuple[str, ...]
    continuation_addresses: tuple[int, ...]
    supporting_depths: tuple[int, ...]
    matched_addresses: tuple[int, ...]
    atomic_key: tuple[int, int, int, int, int]

    @property
    def structural_key(
        self,
    ) -> tuple[
        tuple[int, int, int, int, int],
        int,
        int,
        int,
        tuple[int, ...],
    ]:
        return (
            self.atomic_key,
            len(self.supporting_depths),
            len(self.witnesses),
            len(self.continuation_addresses),
            self.continuation_addresses,
        )


@dataclass(frozen=True, slots=True)
class StructuralFrontierHypothesisV2:
    address: int
    witnesses: tuple[StructuralRolloutWitnessV2, ...]
    trajectory_ids: tuple[str, ...]
    supporting_depths: tuple[int, ...]
    matched_addresses: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class StructuralFrontierResolutionV2:
    query_addresses: tuple[int, ...]
    hypotheses: tuple[StructuralFrontierHypothesisV2, ...]
    terminal_trajectory_ids: tuple[str, ...]
    resolved_address: int | None
    resolved: bool
    ambiguous: bool
    bounded_out: bool
    reason: str


@dataclass(frozen=True, slots=True)
class StructuralRolloutResolutionV2:
    query_addresses: tuple[int, ...]
    shared_prefix_addresses: tuple[int, ...]
    branches: tuple[StructuralRolloutPathV2, ...]
    divergence_index: int | None
    terminal_trajectory_ids: tuple[str, ...]
    exhausted: bool
    ambiguous: bool
    bounded_out: bool
    reason: str


class StructuralRolloutResolverV2:
    """Occurrence-local forward rollout over reconciled V2 structural memory.

    Multiscale evidence selects the structurally strongest observed occurrences.
    Forward continuation then walks only inside each selected stored occurrence.
    The resolver never jumps through a globally shared address and never learns
    from a query.
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
    ) -> None:
        self.trajectories = trajectories
        self.multiscale = MultiscaleStructuralResolverV2(
            trajectories,
            max_depth=max_depth,
            min_occurrences=min_occurrences,
            min_trajectory_count=min_trajectory_count,
            min_size=min_size,
            max_size=max_size,
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
    def _lcs_positions(
        query: tuple[int, ...],
        candidate: tuple[int, ...],
    ) -> tuple[int, ...]:
        if not query or not candidate:
            return ()
        rows = len(query) + 1
        cols = len(candidate) + 1
        dp = [[0] * cols for _ in range(rows)]
        for i in range(1, rows):
            q = query[i - 1]
            for j in range(1, cols):
                if q == candidate[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        i, j = len(query), len(candidate)
        positions: list[int] = []
        while i > 0 and j > 0:
            if query[i - 1] == candidate[j - 1]:
                positions.append(j - 1)
                i -= 1
                j -= 1
            elif dp[i - 1][j] > dp[i][j - 1]:
                i -= 1
            else:
                # Prefer the later candidate position on ties so rollout anchors
                # at the most recent structurally compatible point in occurrence.
                j -= 1
        positions.reverse()
        return tuple(positions)

    @staticmethod
    def _common_prefix(paths: tuple[StructuralRolloutPathV2, ...]) -> tuple[int, ...]:
        if not paths:
            return ()
        limit = min(len(path.continuation_addresses) for path in paths)
        length = 0
        for index in range(limit):
            value = paths[0].continuation_addresses[index]
            if all(path.continuation_addresses[index] == value for path in paths[1:]):
                length += 1
            else:
                break
        return paths[0].continuation_addresses[:length]

    def resolve_addresses(
        self,
        addresses,
        *,
        hierarchy_id: str,
        max_steps: int = 8,
        candidate_limit: int = 64,
        branch_limit: int = 16,
    ) -> StructuralRolloutResolutionV2:
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if candidate_limit < 1:
            raise ValueError("candidate_limit must be >= 1")
        if branch_limit < 1:
            raise ValueError("branch_limit must be >= 1")
        query = self._collapse(addresses)
        if not query:
            raise ValueError("query must contain at least one structural address")

        population = sum(
            1
            for item in self.trajectories.snapshot()
            if item.hierarchy_id == hierarchy_id
        )
        if population == 0:
            return StructuralRolloutResolutionV2(
                query, (), (), None, (), True, False, False, "no-trajectories"
            )

        all_matches = self.multiscale.resolve_addresses(
            query,
            hierarchy_id=hierarchy_id,
            limit=max(1, population),
        )
        if not all_matches:
            return StructuralRolloutResolutionV2(
                query, (), (), None, (), True, False, False, "no-structural-match"
            )

        best_atomic = all_matches[0].atomic_evidence.structural_key
        strongest = tuple(
            match
            for match in all_matches
            if match.atomic_evidence.structural_key == best_atomic
        )
        if len(strongest) > candidate_limit:
            return StructuralRolloutResolutionV2(
                query, (), (), None, (), True, True, True, "candidate-limit-exceeded"
            )

        by_id = {
            item.trajectory_id: item
            for item in self.trajectories.snapshot()
            if item.hierarchy_id == hierarchy_id
        }
        grouped: dict[
            tuple[int, ...],
            list[tuple[StructuralRolloutWitnessV2, tuple[int, ...], tuple[int, ...]]],
        ] = defaultdict(list)
        terminal_ids: set[str] = set()

        for match in strongest:
            trajectory = by_id[match.trajectory_id]
            positions = self._lcs_positions(query, trajectory.addresses)
            if not positions:
                continue
            anchor = positions[-1]
            continuation = trajectory.addresses[anchor + 1 : anchor + 1 + max_steps]
            matched = tuple(trajectory.addresses[index] for index in positions)
            if not continuation:
                terminal_ids.add(trajectory.trajectory_id)
                continue
            witness = StructuralRolloutWitnessV2(
                trajectory_id=trajectory.trajectory_id,
                anchor_index=anchor,
            )
            grouped[continuation].append(
                (witness, tuple(match.supporting_depths), matched)
            )

        paths: list[StructuralRolloutPathV2] = []
        for continuation, members in grouped.items():
            witnesses = tuple(
                sorted(
                    {member[0] for member in members},
                    key=lambda item: (item.trajectory_id, item.anchor_index),
                )
            )
            trajectory_ids = tuple(sorted({item.trajectory_id for item in witnesses}))
            depths = tuple(sorted({depth for member in members for depth in member[1]}))
            matched = tuple(dict.fromkeys(value for member in members for value in member[2]))
            paths.append(
                StructuralRolloutPathV2(
                    witnesses=witnesses,
                    trajectory_ids=trajectory_ids,
                    continuation_addresses=continuation,
                    supporting_depths=depths,
                    matched_addresses=matched,
                    atomic_key=best_atomic,
                )
            )

        paths.sort(key=lambda item: item.structural_key, reverse=True)
        if len(paths) + (1 if terminal_ids else 0) > branch_limit:
            return StructuralRolloutResolutionV2(
                query,
                (),
                (),
                None,
                tuple(sorted(terminal_ids)),
                True,
                True,
                True,
                "branch-limit-exceeded",
            )

        visible = tuple(paths)
        prefix = self._common_prefix(visible)
        if visible:
            outcome_count = len(visible) + (1 if terminal_ids else 0)
            return StructuralRolloutResolutionV2(
                query_addresses=query,
                shared_prefix_addresses=prefix,
                branches=visible,
                divergence_index=(len(prefix) if len(visible) > 1 else None),
                terminal_trajectory_ids=tuple(sorted(terminal_ids)),
                exhausted=False,
                ambiguous=outcome_count > 1,
                bounded_out=False,
                reason=(
                    "competing-forward-outcomes"
                    if outcome_count > 1
                    else "single-forward-path"
                ),
            )
        if terminal_ids:
            return StructuralRolloutResolutionV2(
                query,
                (),
                (),
                None,
                tuple(sorted(terminal_ids)),
                True,
                False,
                False,
                "matched-terminal-occurrence",
            )
        return StructuralRolloutResolutionV2(
            query, (), (), None, (), True, False, False, "no-forward-continuation"
        )

    def frontier_addresses(
        self,
        addresses,
        *,
        hierarchy_id: str,
        candidate_limit: int = 64,
        branch_limit: int = 16,
    ) -> StructuralFrontierResolutionV2:
        rollout = self.resolve_addresses(
            addresses,
            hierarchy_id=hierarchy_id,
            max_steps=1,
            candidate_limit=candidate_limit,
            branch_limit=branch_limit,
        )
        if rollout.bounded_out:
            return StructuralFrontierResolutionV2(
                rollout.query_addresses,
                (),
                rollout.terminal_trajectory_ids,
                None,
                False,
                True,
                True,
                rollout.reason,
            )

        grouped: dict[int, list[StructuralRolloutPathV2]] = defaultdict(list)
        for path in rollout.branches:
            if path.continuation_addresses:
                grouped[path.continuation_addresses[0]].append(path)

        hypotheses: list[StructuralFrontierHypothesisV2] = []
        for address, members in grouped.items():
            witnesses = tuple(
                sorted(
                    {w for member in members for w in member.witnesses},
                    key=lambda item: (item.trajectory_id, item.anchor_index),
                )
            )
            hypotheses.append(
                StructuralFrontierHypothesisV2(
                    address=address,
                    witnesses=witnesses,
                    trajectory_ids=tuple(sorted({tid for m in members for tid in m.trajectory_ids})),
                    supporting_depths=tuple(sorted({d for m in members for d in m.supporting_depths})),
                    matched_addresses=tuple(dict.fromkeys(v for m in members for v in m.matched_addresses)),
                )
            )
        hypotheses.sort(key=lambda item: item.address)
        visible = tuple(hypotheses)
        terminals = rollout.terminal_trajectory_ids
        outcome_count = len(visible) + (1 if terminals else 0)

        if len(visible) == 1 and not terminals:
            return StructuralFrontierResolutionV2(
                rollout.query_addresses,
                visible,
                (),
                visible[0].address,
                True,
                False,
                False,
                "single-frontier",
            )
        if outcome_count > 1:
            return StructuralFrontierResolutionV2(
                rollout.query_addresses,
                visible,
                terminals,
                None,
                False,
                True,
                False,
                (
                    "frontier-competes-with-terminal"
                    if terminals
                    else "competing-frontiers"
                ),
            )
        return StructuralFrontierResolutionV2(
            rollout.query_addresses,
            visible,
            terminals,
            None,
            False,
            False,
            False,
            rollout.reason,
        )
