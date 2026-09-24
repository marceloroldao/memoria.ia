from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from time import perf_counter

from .context_compiler_v2 import ContextCompilerV2
from .resolutive_inference_v2 import ResolutiveInferenceEngineV2
from .structural_trajectory_v2 import StructuralTrajectoryIndex
from .temporal_state_v2 import TemporalStateOperationV2


R14_BENCHMARK_SCHEMA = "memoria.ia-r14-progressive-llm-reduction-v1"


def _json_bytes(value: object) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


@dataclass(frozen=True, slots=True)
class StructuralPreLanguageMeasurementV2:
    case_id: str
    status: str
    resolved_address: int | None
    competing_addresses: tuple[int, ...]
    expected_status: str
    expected_resolved_address: int | None
    correct: bool
    retrieval_trajectory_count: int
    raw_retrieval_context_bytes: int
    compiled_context_bytes: int
    inference_latency_ms: float
    external_calls: int
    llm_calls: int
    semantic_projection: bool
    completed_before_language: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TemporalPreLanguageMeasurementV2:
    case_id: str
    operation: str
    status: str
    payload_addresses: tuple[int, ...]
    previous_payload_addresses: tuple[int, ...]
    removed_addresses: tuple[int, ...]
    added_addresses: tuple[int, ...]
    expected_payload_addresses: tuple[int, ...]
    correct: bool
    observed_history_bytes: int
    compiled_context_bytes: int
    inference_latency_ms: float
    external_calls: int
    llm_calls: int
    semantic_projection: bool
    completed_before_language: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _raw_retrieval_context(
    trajectories: StructuralTrajectoryIndex,
    query_addresses,
    *,
    hierarchy_id: str,
    limit: int = 64,
) -> tuple[dict[str, object], ...]:
    matches = trajectories.resolve_addresses(
        query_addresses,
        hierarchy_id=hierarchy_id,
        limit=limit,
    )
    ids = {match.trajectory_id for match in matches}
    return tuple(
        {
            "trajectory_id": item.trajectory_id,
            "source_id": item.source_id,
            "sequence": item.sequence,
            "addresses": list(item.addresses),
            "observation_id": item.observation_id,
        }
        for item in trajectories.snapshot()
        if item.trajectory_id in ids
    )


def measure_structural_pre_language_v2(
    engine: ResolutiveInferenceEngineV2,
    query_addresses,
    *,
    hierarchy_id: str,
    case_id: str,
    expected_status: str,
    expected_resolved_address: int | None = None,
) -> StructuralPreLanguageMeasurementV2:
    raw = _raw_retrieval_context(
        engine.trajectories,
        query_addresses,
        hierarchy_id=hierarchy_id,
    )
    started = perf_counter()
    result = engine.infer_structural(
        query_addresses,
        hierarchy_id=hierarchy_id,
    )
    elapsed_ms = (perf_counter() - started) * 1000.0
    packet = ContextCompilerV2.compile_structural(result)

    correct = result.status == expected_status
    if expected_resolved_address is not None:
        correct = correct and result.resolved_address == expected_resolved_address

    return StructuralPreLanguageMeasurementV2(
        case_id=str(case_id),
        status=result.status,
        resolved_address=result.resolved_address,
        competing_addresses=result.competing_addresses,
        expected_status=str(expected_status),
        expected_resolved_address=expected_resolved_address,
        correct=correct,
        retrieval_trajectory_count=len(raw),
        raw_retrieval_context_bytes=_json_bytes(raw),
        compiled_context_bytes=_json_bytes(
            {
                "addresses": packet.addresses,
                "status": packet.status,
                "resolved_state": packet.resolved_state,
                "competing_states": packet.competing_states,
                "trajectory_ids": packet.trajectory_ids,
                "provenance_ids": packet.provenance_ids,
                "conflicts": packet.conflicts,
                "source_tier": packet.source_tier,
                "uncertainty": packet.uncertainty,
            }
        ),
        inference_latency_ms=elapsed_ms,
        external_calls=result.diagnostics.external_calls,
        llm_calls=result.diagnostics.llm_calls,
        semantic_projection=result.diagnostics.semantic_projection,
        completed_before_language=correct and result.status in {"resolved", "ambiguous", "terminal", "unresolved"},
    )


def measure_temporal_pre_language_v2(
    engine: ResolutiveInferenceEngineV2,
    state_address: int,
    *,
    hierarchy_id: str,
    case_id: str,
    operation: TemporalStateOperationV2 | str,
    expected_payload_addresses: tuple[int, ...],
) -> TemporalPreLanguageMeasurementV2:
    if engine.temporal is None:
        raise RuntimeError("state_reader is required for temporal benchmark")
    history = engine.temporal.state.history(
        int(state_address),
        hierarchy_id=hierarchy_id,
    )
    started = perf_counter()
    result = engine.infer_temporal_state(
        state_address,
        hierarchy_id=hierarchy_id,
        operation=operation,
    )
    elapsed_ms = (perf_counter() - started) * 1000.0
    packet = ContextCompilerV2.compile_temporal(result)

    correct = (
        result.status == "resolved"
        and packet.payload_addresses == tuple(expected_payload_addresses)
    )
    return TemporalPreLanguageMeasurementV2(
        case_id=str(case_id),
        operation=packet.operation,
        status=result.status,
        payload_addresses=packet.payload_addresses,
        previous_payload_addresses=packet.previous_payload_addresses,
        removed_addresses=packet.removed_addresses,
        added_addresses=packet.added_addresses,
        expected_payload_addresses=tuple(expected_payload_addresses),
        correct=correct,
        observed_history_bytes=_json_bytes(
            [
                {
                    "revision_id": revision.revision_id,
                    "sequence": revision.sequence,
                    "payload_addresses": revision.payload_addresses,
                    "trajectory_ids": revision.trajectory_ids,
                    "provenance_ids": revision.provenance_ids,
                }
                for revision in history
            ]
        ),
        compiled_context_bytes=_json_bytes(
            {
                "state_address": packet.state_address,
                "operation": packet.operation,
                "status": packet.status,
                "payload_addresses": packet.payload_addresses,
                "previous_payload_addresses": packet.previous_payload_addresses,
                "removed_addresses": packet.removed_addresses,
                "added_addresses": packet.added_addresses,
                "trajectory_ids": packet.trajectory_ids,
                "provenance_ids": packet.provenance_ids,
                "uncertainty": packet.uncertainty,
            }
        ),
        inference_latency_ms=elapsed_ms,
        external_calls=result.external_calls,
        llm_calls=result.llm_calls,
        semantic_projection=result.semantic_projection,
        completed_before_language=correct,
    )


def summarize_r14_measurements_v2(
    *,
    structural: tuple[StructuralPreLanguageMeasurementV2, ...],
    temporal: tuple[TemporalPreLanguageMeasurementV2, ...],
) -> dict[str, object]:
    all_rows = (*structural, *temporal)
    return {
        "schema": R14_BENCHMARK_SCHEMA,
        "structural_cases": [row.as_dict() for row in structural],
        "temporal_cases": [row.as_dict() for row in temporal],
        "summary": {
            "case_count": len(all_rows),
            "correct_before_language": sum(1 for row in all_rows if row.correct),
            "external_calls": sum(row.external_calls for row in all_rows),
            "llm_calls": sum(row.llm_calls for row in all_rows),
            "semantic_projection_cases": sum(1 for row in all_rows if row.semantic_projection),
        },
        "interpretation": {
            "control": "raw structural retrieval context is a retrieval-only control, not a full RAG system",
            "language": "machine-consumable cognitive results are measured before optional verbalization",
            "paraphrase": "natural-language paraphrase is not claimed by this address-level benchmark",
            "latency": "latency is observed wall-clock measurement and is not a deterministic gate",
        },
    }
