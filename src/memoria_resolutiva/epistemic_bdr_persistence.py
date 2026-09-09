from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol

from .bdr_atomic_bridge import CtypesAtomicBDR
from .evidence_temporal_bridge import (
    EpistemicSource,
    EvidenceProjection,
    EvidenceTemporalBridge,
)
from .learning_gate import EpistemicLearningGate, LearningDecision
from .response_validator import ResponseValidator


_SCHEMA_VERSION = 1
_ROOT_KEY = "memoria.epistemic.v1/root"


class AtomicBatchBackend(Protocol):
    def write_batch(self, puts: list[tuple[str, bytes]]) -> int: ...
    def get(self, key: str) -> bytes | None: ...


@dataclass(frozen=True, slots=True)
class EpistemicBDRStats:
    projections: int
    decisions: int
    response_ids: int
    physical_records: int
    bdr_sequence: int


def _encode_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _decode_json(data: bytes | None, key: str) -> object:
    if data is None:
        raise ValueError(f"missing BDR epistemic record: {key}")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid BDR epistemic JSON record: {key}") from exc


def save_epistemic_audit_to_backend(
    backend: AtomicBatchBackend,
    bridge: EvidenceTemporalBridge,
    gate: EpistemicLearningGate,
    response_validator: ResponseValidator | None = None,
) -> EpistemicBDRStats:
    """Persist epistemic audit as one independent atomic BDR batch.

    The namespace is intentionally separate from topological CURRENT/HISTORY. It stores
    projection/learning audit and, when supplied, the Response Validator idempotency
    boundary. ``response_ids`` is additive inside schema v1 so older manifests that do
    not contain the field remain readable.
    """
    puts: list[tuple[str, bytes]] = []
    projection_keys: list[str] = []
    decision_keys: list[str] = []

    for index, projection in enumerate(bridge.iter_projections()):
        key = f"memoria.epistemic.v1/projection/{index:020d}"
        projection_keys.append(key)
        event = projection.temporal_event
        puts.append((key, _encode_json({
            "evidence_id": projection.evidence_id,
            "epistemic_source": projection.epistemic_source.value,
            "promoted": projection.promoted,
            "reason": projection.reason,
            "provenance": projection.provenance,
            "origin": projection.origin,
            "confidence": projection.confidence,
            "temporal_event_id": None if event is None else event.event_id,
            "temporal_sequence": None if event is None else event.sequence,
        })))

    for index, decision in enumerate(gate.iter_decisions()):
        key = f"memoria.epistemic.v1/decision/{index:020d}"
        decision_keys.append(key)
        puts.append((key, _encode_json({
            "decision_id": decision.decision_id,
            "candidate_evidence_id": decision.candidate_evidence_id,
            "accepted": decision.accepted,
            "validator_source": decision.validator_source.value,
            "validator_id": decision.validator_id,
            "reason": decision.reason,
            "promoted_evidence_id": decision.promoted_evidence_id,
        })))

    response_ids = () if response_validator is None else response_validator.iter_response_ids()
    manifest = {
        "schema_version": _SCHEMA_VERSION,
        "projection_keys": projection_keys,
        "decision_keys": decision_keys,
        "response_ids": list(response_ids),
    }
    puts.append((_ROOT_KEY, _encode_json(manifest)))
    sequence = backend.write_batch(puts)
    return EpistemicBDRStats(
        projections=len(projection_keys),
        decisions=len(decision_keys),
        response_ids=len(response_ids),
        physical_records=len(puts),
        bdr_sequence=sequence,
    )


def load_epistemic_audit_from_backend(
    backend: AtomicBatchBackend,
    bridge: EvidenceTemporalBridge,
    gate: EpistemicLearningGate,
    response_validator: ResponseValidator | None = None,
) -> EpistemicBDRStats:
    manifest_raw = _decode_json(backend.get(_ROOT_KEY), _ROOT_KEY)
    if not isinstance(manifest_raw, dict):
        raise ValueError("invalid BDR epistemic root manifest")
    if int(manifest_raw.get("schema_version", 0)) != _SCHEMA_VERSION:
        raise ValueError("unsupported BDR epistemic snapshot schema version")

    response_ids_raw = manifest_raw.get("response_ids", [])
    if not isinstance(response_ids_raw, list):
        raise ValueError("invalid BDR response validator id list")
    response_ids = tuple(str(value).strip() for value in response_ids_raw)
    if any(not value for value in response_ids):
        raise ValueError("response validator id must be non-empty")
    if len(response_ids) != len(set(response_ids)):
        raise ValueError("response validator audit contains duplicate response_id")

    events_by_sequence = {event.sequence: event for event in bridge.store.iter_events()}
    projections: list[EvidenceProjection] = []
    for key_value in manifest_raw.get("projection_keys", []):
        key = str(key_value)
        record = _decode_json(backend.get(key), key)
        if not isinstance(record, dict):
            raise ValueError(f"invalid BDR epistemic projection: {key}")
        try:
            source = EpistemicSource(str(record["epistemic_source"]))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"invalid epistemic source in projection: {key}") from exc
        promoted = bool(record["promoted"])
        sequence_raw = record.get("temporal_sequence")
        event_id_raw = record.get("temporal_event_id")
        event = None
        if promoted:
            if sequence_raw is None or event_id_raw is None:
                raise ValueError("promoted projection is missing temporal event reference")
            event = events_by_sequence.get(int(sequence_raw))
            if event is None or event.event_id != str(event_id_raw):
                raise ValueError("epistemic projection references unknown temporal event")
        elif sequence_raw is not None or event_id_raw is not None:
            raise ValueError("quarantined projection contains temporal event reference")
        projections.append(EvidenceProjection(
            evidence_id=str(record["evidence_id"]),
            epistemic_source=source,
            promoted=promoted,
            reason=str(record["reason"]),
            temporal_event=event,
            provenance=str(record["provenance"]),
            origin=str(record["origin"]),
            confidence=float(record["confidence"]),
        ))

    decisions: list[LearningDecision] = []
    for key_value in manifest_raw.get("decision_keys", []):
        key = str(key_value)
        record = _decode_json(backend.get(key), key)
        if not isinstance(record, dict):
            raise ValueError(f"invalid BDR learning decision: {key}")
        try:
            validator_source = EpistemicSource(str(record["validator_source"]))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"invalid validator source in learning decision: {key}") from exc
        decisions.append(LearningDecision(
            decision_id=str(record["decision_id"]),
            candidate_evidence_id=str(record["candidate_evidence_id"]),
            accepted=bool(record["accepted"]),
            validator_source=validator_source,
            validator_id=str(record["validator_id"]),
            reason=str(record["reason"]),
            promoted_evidence_id=(
                None if record.get("promoted_evidence_id") is None
                else str(record["promoted_evidence_id"])
            ),
        ))

    # Validate every record before mutating the runtime audit surfaces.
    bridge.restore_projection_audit(projections)
    try:
        gate.restore_decisions(decisions)
    except Exception:
        bridge.restore_projection_audit(())
        raise
    if response_validator is not None:
        try:
            response_validator.restore_response_ids(response_ids)
        except Exception:
            # The response-id list is fully prevalidated above; this protects callers
            # that accidentally provide a non-empty validator instance.
            bridge.restore_projection_audit(())
            raise

    return EpistemicBDRStats(
        projections=len(projections),
        decisions=len(decisions),
        response_ids=len(response_ids),
        physical_records=len(projections) + len(decisions) + 1,
        bdr_sequence=0,
    )


def save_epistemic_audit_bdr(
    root: str | Path,
    library_path: str | Path,
    bridge: EvidenceTemporalBridge,
    gate: EpistemicLearningGate,
    response_validator: ResponseValidator | None = None,
) -> EpistemicBDRStats:
    with CtypesAtomicBDR(root, library_path) as backend:
        return save_epistemic_audit_to_backend(backend, bridge, gate, response_validator)


def load_epistemic_audit_bdr(
    root: str | Path,
    library_path: str | Path,
    bridge: EvidenceTemporalBridge,
    gate: EpistemicLearningGate,
    response_validator: ResponseValidator | None = None,
) -> EpistemicBDRStats:
    with CtypesAtomicBDR(root, library_path) as backend:
        stats = load_epistemic_audit_from_backend(backend, bridge, gate, response_validator)
        return EpistemicBDRStats(
            projections=stats.projections,
            decisions=stats.decisions,
            response_ids=stats.response_ids,
            physical_records=stats.physical_records,
            bdr_sequence=backend.last_sequence(),
        )
