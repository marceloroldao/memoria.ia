from memoria_resolutiva.evolving_address_state_v2 import EvolvingAddressStateJournalV2
from memoria_resolutiva.progressive_llm_benchmark_v2 import (
    R14_BENCHMARK_SCHEMA,
    measure_structural_pre_language_v2,
    measure_temporal_pre_language_v2,
    summarize_r14_measurements_v2,
)
from memoria_resolutiva.resolutive_inference_v2 import ResolutiveInferenceEngineV2
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex


def _index():
    index = StructuralTrajectoryIndex()
    rows = [
        ("dominant:a", [10, 20, 30]),
        ("dominant:b", [10, 20, 30]),
        ("dominant:c", [10, 20, 30]),
        ("competing", [10, 20, 40]),
        ("ambiguous:a", [5, 6, 7]),
        ("ambiguous:b", [5, 6, 8]),
    ]
    for sequence, (source, addresses) in enumerate(rows):
        index.ingest_addresses(
            addresses,
            hierarchy_id="r14",
            source_id=source,
            sequence=sequence,
            observation_id=f"obs:{source}",
        )
    return index


def test_r14_structural_measurements_report_native_resolution_conflict_and_negative_without_llm():
    engine = ResolutiveInferenceEngineV2(_index())

    resolved = measure_structural_pre_language_v2(
        engine,
        [10, 20],
        hierarchy_id="r14",
        case_id="resolved",
        expected_status="resolved",
        expected_resolved_address=30,
    )
    ambiguous = measure_structural_pre_language_v2(
        engine,
        [5, 6],
        hierarchy_id="r14",
        case_id="ambiguous",
        expected_status="ambiguous",
    )
    negative = measure_structural_pre_language_v2(
        engine,
        [999, 1000],
        hierarchy_id="r14",
        case_id="negative",
        expected_status="unresolved",
    )

    assert resolved.correct and resolved.resolved_address == 30
    assert ambiguous.correct and ambiguous.competing_addresses == (7, 8)
    assert negative.correct and negative.status == "unresolved"
    assert resolved.retrieval_trajectory_count == 4
    assert resolved.raw_retrieval_context_bytes > 0
    assert resolved.compiled_context_bytes > 0
    for row in (resolved, ambiguous, negative):
        assert row.external_calls == 0
        assert row.llm_calls == 0
        assert row.semantic_projection is False
        assert row.completed_before_language is True
        assert row.inference_latency_ms >= 0.0


def test_r14_temporal_current_and_change_are_measured_before_language():
    journal = EvolvingAddressStateJournalV2()
    journal.append(
        77,
        hierarchy_id="r14",
        sequence=1,
        payload_addresses=[700],
        trajectory_ids=["t:old"],
        provenance_ids=["p:old"],
    )
    journal.append(
        77,
        hierarchy_id="r14",
        sequence=2,
        payload_addresses=[800],
        trajectory_ids=["t:new"],
        provenance_ids=["p:new"],
    )
    engine = ResolutiveInferenceEngineV2(_index(), state_reader=journal)

    current = measure_temporal_pre_language_v2(
        engine,
        77,
        hierarchy_id="r14",
        case_id="current",
        operation="current",
        expected_payload_addresses=(800,),
    )
    change = measure_temporal_pre_language_v2(
        engine,
        77,
        hierarchy_id="r14",
        case_id="change",
        operation="change",
        expected_payload_addresses=(800,),
    )

    assert current.correct
    assert current.payload_addresses == (800,)
    assert change.correct
    assert change.previous_payload_addresses == (700,)
    assert change.removed_addresses == (700,)
    assert change.added_addresses == (800,)
    assert current.llm_calls == change.llm_calls == 0
    assert current.external_calls == change.external_calls == 0


def test_r14_summary_does_not_mislabel_retrieval_control_as_full_rag():
    engine = ResolutiveInferenceEngineV2(_index())
    row = measure_structural_pre_language_v2(
        engine,
        [10, 20],
        hierarchy_id="r14",
        case_id="resolved",
        expected_status="resolved",
        expected_resolved_address=30,
    )
    report = summarize_r14_measurements_v2(structural=(row,), temporal=())

    assert report["schema"] == R14_BENCHMARK_SCHEMA
    assert report["summary"]["correct_before_language"] == 1
    assert report["summary"]["external_calls"] == 0
    assert report["summary"]["llm_calls"] == 0
    assert "not a full RAG system" in report["interpretation"]["control"]
    assert "not claimed" in report["interpretation"]["paraphrase"]
