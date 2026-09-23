from __future__ import annotations

from pathlib import Path

from memoria_resolutiva.persistent_structural_trajectory_v2 import (
    PersistentStructuralTrajectoryRuntimeV2,
)
from memoria_resolutiva.structural_branch_state_v2 import (
    DynamicStructuralBranchResolverV2,
)
from memoria_resolutiva.structural_observation import StructuralObservationStore
from memoria_resolutiva.structural_rollout_v2 import StructuralRolloutResolverV2
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex


def _index(rows, *, hierarchy_id="h"):
    index = StructuralTrajectoryIndex()
    for sequence, addresses in enumerate(rows):
        index.ingest_addresses(
            addresses,
            hierarchy_id=hierarchy_id,
            source_id=f"source:{sequence}",
            sequence=sequence,
        )
    return index


def _event(sequence: int, trail: list[int]) -> dict:
    return {
        "version": 1,
        "source_id": f"sensor:{sequence}",
        "sequence": sequence,
        "byte_offset": sequence * 16,
        "byte_length": 16,
        "trail": trail,
        "relation_ids": [],
        "signature": f"{sequence + 1:016x}",
        "resolution": 2,
    }


def test_rollout_preserves_shared_prefix_until_real_divergence():
    index = _index([
        [1, 2, 3, 4],
        [1, 2, 3, 5],
    ])
    resolver = StructuralRolloutResolverV2(index)

    result = resolver.resolve_addresses([1, 2], hierarchy_id="h")

    assert result.exhausted is False
    assert result.ambiguous is True
    assert result.shared_prefix_addresses == (3,)
    assert result.divergence_index == 1
    assert {path.continuation_addresses for path in result.branches} == {
        (3, 4),
        (3, 5),
    }


def test_frontier_groups_independent_occurrences_with_same_next_address():
    index = _index([
        [1, 2, 3, 4],
        [1, 2, 3, 5],
    ])
    resolver = StructuralRolloutResolverV2(index)

    result = resolver.frontier_addresses([1, 2], hierarchy_id="h")

    assert result.resolved is True
    assert result.resolved_address == 3
    assert result.ambiguous is False
    assert len(result.hypotheses) == 1
    assert len(result.hypotheses[0].trajectory_ids) == 2


def test_weaker_hub_match_cannot_hitchhike_into_rollout():
    index = _index([
        [1, 2, 3, 9],
        [2, 8],
        [2, 7],
    ])
    resolver = StructuralRolloutResolverV2(index)

    result = resolver.resolve_addresses([1, 2, 3], hierarchy_id="h")

    assert result.exhausted is False
    assert len(result.branches) == 1
    assert result.branches[0].continuation_addresses == (9,)
    assert result.branches[0].trajectory_ids == (index.snapshot()[0].trajectory_id,)


def test_terminal_and_continuing_outcomes_remain_competing_until_new_observation():
    index = _index([
        [1, 2],
        [1, 2, 3],
    ])
    rollout = StructuralRolloutResolverV2(index).resolve_addresses(
        [1, 2],
        hierarchy_id="h",
    )

    assert rollout.exhausted is False
    assert rollout.ambiguous is True
    assert len(rollout.branches) == 1
    assert rollout.branches[0].continuation_addresses == (3,)
    assert len(rollout.terminal_trajectory_ids) == 1

    frontier = StructuralRolloutResolverV2(index).frontier_addresses(
        [1, 2],
        hierarchy_id="h",
    )
    assert frontier.resolved is False
    assert frontier.ambiguous is True
    assert frontier.reason == "frontier-competes-with-terminal"
    assert len(frontier.terminal_trajectory_ids) == 1

    dynamic = DynamicStructuralBranchResolverV2(index)
    state = dynamic.begin_addresses([1, 2], hierarchy_id="h")
    assert state.ambiguous is True
    assert len(state.terminal_trajectory_ids) == 1

    advanced = dynamic.observe_address(state, 3)
    assert advanced.ambiguous is False
    assert advanced.terminal is True
    assert advanced.terminal_trajectory_ids == ()
    assert set(advanced.eliminated_trajectory_ids) == set(state.terminal_trajectory_ids)


def test_dynamic_observation_narrows_branches_without_mutating_memory():
    index = _index([
        [1, 2, 3, 4],
        [1, 2, 3, 5],
    ])
    before = index.snapshot()
    dynamic = DynamicStructuralBranchResolverV2(index)

    state = dynamic.begin_addresses([1, 2], hierarchy_id="h")
    assert state.ambiguous is True
    assert len(state.active) == 2

    state = dynamic.observe_address(state, 3)
    assert state.ambiguous is True
    assert {branch.remaining_addresses for branch in state.active} == {(4,), (5,)}

    state = dynamic.observe_address(state, 4)
    assert state.exhausted is False
    assert state.ambiguous is False
    assert state.terminal is True
    assert len(state.active) == 1
    assert index.snapshot() == before


def test_repeated_observation_does_not_consume_an_extra_step():
    index = _index([[1, 2, 3, 4]])
    dynamic = DynamicStructuralBranchResolverV2(index)

    state = dynamic.begin_addresses([1, 2], hierarchy_id="h")
    first = dynamic.observe_address(state, 3)
    replay = dynamic.observe_address(first, 3)

    assert replay == first
    assert replay.active[0].remaining_addresses == (4,)
    assert replay.active[0].consumed_steps == 1


def test_incompatible_observation_exhausts_hypotheses_but_keeps_occurrences():
    index = _index([
        [1, 2, 3, 4],
        [1, 2, 3, 5],
    ])
    before = index.snapshot()
    dynamic = DynamicStructuralBranchResolverV2(index)

    state = dynamic.begin_addresses([1, 2], hierarchy_id="h")
    exhausted = dynamic.observe_address(state, 99)

    assert exhausted.exhausted is True
    assert exhausted.active == ()
    assert set(exhausted.eliminated_trajectory_ids) == {
        trajectory.trajectory_id for trajectory in before
    }
    assert index.snapshot() == before


def test_recovery_reanchors_only_from_new_observation_geometry():
    index = _index([
        [1, 2, 3, 4],
        [1, 2, 3, 5],
        [9, 10, 11],
    ])
    dynamic = DynamicStructuralBranchResolverV2(index)

    state = dynamic.begin_addresses([1, 2], hierarchy_id="h")
    exhausted = dynamic.observe_address(state, 99)
    recovery = dynamic.recover_addresses(exhausted, [9, 10])

    assert recovery.recovered_any is True
    assert recovery.matched_suffix == (9, 10)
    assert len(recovery.recovered.active) == 1
    assert recovery.recovered.active[0].remaining_addresses == (11,)
    assert 99 not in recovery.recovered.seed_addresses


def test_recovery_may_use_shorter_suffix_only_when_longer_suffix_is_unseen():
    index = _index([[9, 10, 11]])
    dynamic = DynamicStructuralBranchResolverV2(index)
    exhausted = dynamic.begin_addresses([500], hierarchy_id="h")
    assert exhausted.exhausted is True

    recovery = dynamic.recover_addresses(exhausted, [99, 9, 10])

    assert recovery.recovered_any is True
    assert recovery.matched_suffix == (9, 10)
    assert recovery.recovered.active[0].remaining_addresses == (11,)


def test_terminal_full_suffix_blocks_shorter_hub_stitching():
    index = _index([
        [9, 10],
        [10, 11],
    ])
    dynamic = DynamicStructuralBranchResolverV2(index)
    exhausted = dynamic.begin_addresses([500], hierarchy_id="h")
    assert exhausted.exhausted is True

    before = index.snapshot()
    recovery = dynamic.recover_addresses(exhausted, [9, 10])

    assert recovery.recovered_any is False
    assert recovery.matched_suffix == (9, 10)
    assert recovery.recovered.reason == "recovery-matched-terminal"
    assert recovery.recovered.active == ()
    assert index.snapshot() == before


def test_recovery_uses_rightmost_witness_inside_one_occurrence():
    index = _index([
        [9, 10, 11, 9, 10],
    ])
    dynamic = DynamicStructuralBranchResolverV2(index)
    exhausted = dynamic.begin_addresses([500], hierarchy_id="h")

    recovery = dynamic.recover_addresses(exhausted, [9, 10])

    assert recovery.recovered_any is False
    assert recovery.matched_suffix == (9, 10)
    assert recovery.recovered.terminal is True
    assert recovery.recovered.reason == "recovery-matched-terminal"


def test_recovery_fails_closed_when_branch_limit_would_hide_equivalent_futures():
    index = _index([
        [9, 10, 11],
        [9, 10, 12],
        [9, 10, 13],
    ])
    dynamic = DynamicStructuralBranchResolverV2(index)
    exhausted = dynamic.begin_addresses([500], hierarchy_id="h")

    recovery = dynamic.recover_addresses(
        exhausted,
        [9, 10],
        branch_limit=2,
    )

    assert recovery.recovered_any is False
    assert recovery.recovered.bounded_out is True
    assert recovery.recovered.reason == "recovery-limit-exceeded"


def test_rollout_fails_closed_when_candidate_limit_would_truncate_tied_evidence():
    index = _index([
        [1, 2, 3],
        [1, 2, 4],
        [1, 2, 5],
    ])
    resolver = StructuralRolloutResolverV2(index)

    result = resolver.resolve_addresses(
        [1, 2],
        hierarchy_id="h",
        candidate_limit=2,
    )

    assert result.exhausted is True
    assert result.bounded_out is True
    assert result.reason == "candidate-limit-exceeded"
    assert result.branches == ()


def test_branching_is_deterministic_after_persistent_cold_reopen(tmp_path: Path):
    observations = StructuralObservationStore(
        tmp_path / "observations",
        backend="sqlite",
        allow_fallback=False,
    )
    for sequence, trail in enumerate(([1, 2, 3, 4], [1, 2, 3, 5])):
        observations.append(
            _event(sequence, list(trail)),
            provenance={"hierarchy_id": "h", "source_kind": "test"},
        )

    first = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    first_result = StructuralRolloutResolverV2(first.index).resolve_addresses(
        [1, 2],
        hierarchy_id="h",
    )

    restarted = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    restarted_result = StructuralRolloutResolverV2(restarted.index).resolve_addresses(
        [1, 2],
        hierarchy_id="h",
    )

    assert restarted.replayed_on_open == 0
    assert restarted_result == first_result
