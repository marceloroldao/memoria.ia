from __future__ import annotations

from memoria_resolutiva.evolving_address_state_v2 import EvolvingAddressStateJournalV2
from memoria_resolutiva.persistent_structural_trajectory_v2 import PersistentStructuralTrajectoryRuntimeV2
from memoria_resolutiva.structural_observation import StructuralObservationStore
from memoria_resolutiva.resolutive_inference_v2 import ResolutiveInferenceEngineV2
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex


def _index(rows, *, hierarchy_id="r9"):
    index = StructuralTrajectoryIndex()
    for sequence, (source_id, addresses) in enumerate(rows):
        index.ingest_addresses(
            addresses,
            hierarchy_id=hierarchy_id,
            source_id=source_id,
            sequence=sequence,
            observation_id=f"obs:{source_id}",
        )
    return index


def _assert_zero_llm(result):
    diagnostics = getattr(result, "diagnostics", result)
    assert diagnostics.external_calls == 0
    assert diagnostics.llm_calls == 0
    assert diagnostics.semantic_projection is False


def test_r9_recurrence_dominates_without_deleting_competing_evidence():
    index = _index([
        ("dominant-1", [10, 20, 30]),
        ("competing", [10, 20, 40]),
        ("dominant-2", [10, 20, 30]),
        ("dominant-3", [10, 20, 30]),
    ])
    before = index.snapshot()
    result = ResolutiveInferenceEngineV2(index).infer_structural([10, 20], hierarchy_id="r9")

    assert result.status == "resolved"
    assert result.resolved_address == 30
    assert result.provenance_ids == ("obs:dominant-1", "obs:dominant-2", "obs:dominant-3")
    assert any(t.addresses[-1] == 40 for t in index.snapshot())
    assert index.snapshot() == before
    _assert_zero_llm(result)


def test_r9_multiple_similar_contexts_and_distractors_do_not_cross_stitch():
    index = _index([
        ("ctx-a1", [1, 2, 100]),
        ("ctx-a2", [1, 2, 100]),
        ("ctx-b1", [1, 3, 200]),
        ("ctx-b2", [1, 3, 200]),
        ("distractor-1", [9, 2, 999]),
        ("distractor-2", [1, 8, 888]),
    ])
    engine = ResolutiveInferenceEngineV2(index)

    left = engine.infer_structural([1, 2], hierarchy_id="r9")
    right = engine.infer_structural([1, 3], hierarchy_id="r9")
    unknown = engine.infer_structural([2, 3], hierarchy_id="r9")

    assert (left.status, left.resolved_address) == ("resolved", 100)
    assert (right.status, right.resolved_address) == ("resolved", 200)
    assert unknown.status == "ambiguous"
    assert unknown.resolved_address is None
    assert "direct-structural-ambiguity" in unknown.conflicts
    _assert_zero_llm(left)
    _assert_zero_llm(right)
    _assert_zero_llm(unknown)


def test_r9_competing_evidence_stays_ambiguous_and_negative_stays_unresolved():
    index = _index([
        ("a", [5, 6, 7]),
        ("b", [5, 6, 8]),
    ])
    engine = ResolutiveInferenceEngineV2(index)

    competing = engine.infer_structural([5, 6], hierarchy_id="r9")
    negative = engine.infer_structural([500, 600], hierarchy_id="r9")

    assert competing.status == "ambiguous"
    assert competing.competing_addresses == (7, 8)
    assert negative.status == "unresolved"
    assert negative.resolved_address is None
    _assert_zero_llm(competing)
    _assert_zero_llm(negative)


def test_r9_query_is_immutable_and_repeatable():
    index = _index([
        ("a", [21, 22, 23]),
        ("b", [21, 22, 23]),
    ])
    engine = ResolutiveInferenceEngineV2(index)
    before = index.snapshot()

    first = engine.infer_structural([21, 22], hierarchy_id="r9")
    middle = index.snapshot()
    second = engine.infer_structural([21, 22], hierarchy_id="r9")
    after = index.snapshot()

    assert first == second
    assert before == middle == after
    _assert_zero_llm(first)


def test_r9_current_previous_and_change_are_explicit_zero_llm_operations():
    index = _index([("trajectory", [1, 2, 3])])
    journal = EvolvingAddressStateJournalV2()
    journal.append(
        77,
        hierarchy_id="r9",
        sequence=1,
        payload_addresses=[700],
        trajectory_ids=["t:old"],
        provenance_ids=["p:old"],
    )
    journal.append(
        77,
        hierarchy_id="r9",
        sequence=2,
        payload_addresses=[800],
        trajectory_ids=["t:new"],
        provenance_ids=["p:new"],
    )
    engine = ResolutiveInferenceEngineV2(index, state_reader=journal)

    current = engine.infer_temporal_state(77, hierarchy_id="r9", operation="current")
    previous = engine.infer_temporal_state(77, hierarchy_id="r9", operation="previous")
    change = engine.infer_temporal_state(77, hierarchy_id="r9", operation="change")

    assert current.temporal.revision is not None
    assert current.temporal.revision.payload_addresses == (800,)
    assert previous.temporal.revision is not None
    assert previous.temporal.revision.payload_addresses == (700,)
    assert change.temporal.change is not None
    assert change.temporal.change.removed_addresses == (700,)
    assert change.temporal.change.added_addresses == (800,)
    _assert_zero_llm(current)
    _assert_zero_llm(previous)
    _assert_zero_llm(change)


def test_r9_forward_and_reverse_traversal_are_consistent():
    index = _index([
        ("a", [31, 32, 33]),
        ("b", [31, 32, 33]),
    ])
    forward = index.frontier([31, 32], hierarchy_id="r9", direction="forward")
    reverse = index.frontier([33], hierarchy_id="r9", direction="reverse")

    assert forward.resolved_address == 33
    assert reverse.resolved_address == 32


def test_r9_cold_reopen_preserves_decision_surface(tmp_path):
    observations = StructuralObservationStore(
        tmp_path / "observations",
        backend="sqlite",
        allow_fallback=False,
    )
    for sequence, trail in enumerate(([41, 42, 43], [41, 42, 43], [41, 42, 44])):
        observations.append(
            {
                "version": 1,
                "source_id": f"r9:{sequence}",
                "sequence": sequence,
                "byte_offset": sequence * 16,
                "byte_length": 16,
                "trail": list(trail),
                "relation_ids": [],
                "signature": f"{sequence + 1:016x}",
                "resolution": 2,
            },
            provenance={"hierarchy_id": "r9", "source_kind": "r9-benchmark"},
        )

    first = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    before = first.snapshot_bytes()
    first_result = ResolutiveInferenceEngineV2(first.index).infer_structural(
        [41, 42],
        hierarchy_id="r9",
    )

    reopened = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    second_result = ResolutiveInferenceEngineV2(reopened.index).infer_structural(
        [41, 42],
        hierarchy_id="r9",
    )

    assert reopened.replayed_on_open == 0
    assert reopened.snapshot_bytes() == before
    assert first_result.status == second_result.status == "resolved"
    assert first_result.resolved_address == second_result.resolved_address == 43
    _assert_zero_llm(first_result)
    _assert_zero_llm(second_result)
