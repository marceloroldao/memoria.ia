from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol

from .bdr_atomic_bridge import CtypesAtomicBDR
from .evidence_core import EvidenceCore, EvidenceEdge


_SCHEMA_VERSION = 1
_ROOT_KEY = "memoria.evidence.v1/root"


class AtomicBatchBackend(Protocol):
    def write_batch(self, puts: list[tuple[str, bytes]]) -> int: ...
    def get(self, key: str) -> bytes | None: ...


@dataclass(frozen=True, slots=True)
class EvidenceBDRStats:
    evidence_rows: int
    physical_records: int
    bdr_sequence: int


def _encode_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _decode_json(data: bytes | None, key: str) -> object:
    if data is None:
        raise ValueError(f"missing BDR evidence record: {key}")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid BDR evidence JSON record: {key}") from exc


def save_evidence_catalog_to_backend(
    backend: AtomicBatchBackend,
    evidence: EvidenceCore,
) -> EvidenceBDRStats:
    """Persist the complete EvidenceCore edge catalog as one logical BDR batch.

    This namespace is intentionally separate from factual temporal state and from
    epistemic audit. Evidence rows preserve source/provenance and are not promoted
    merely because they are durable.
    """
    rows = evidence.iter_evidence()
    evidence_ids = [row.evidence_id for row in rows]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("EvidenceCore catalog contains duplicate evidence_id")

    puts: list[tuple[str, bytes]] = []
    record_keys: list[str] = []
    for index, row in enumerate(rows):
        key = f"memoria.evidence.v1/edge/{index:020d}"
        record_keys.append(key)
        puts.append((key, _encode_json({
            "subject": row.subject,
            "predicate": row.predicate,
            "object": row.object,
            "evidence_id": row.evidence_id,
            "source_text": row.source_text,
            "namespace": row.namespace,
            "epoch": row.epoch,
            "provenance": row.provenance,
            "origin": row.origin,
            "confidence": row.confidence,
        })))

    puts.append((_ROOT_KEY, _encode_json({
        "schema_version": _SCHEMA_VERSION,
        "record_keys": record_keys,
    })))
    sequence = backend.write_batch(puts)
    return EvidenceBDRStats(
        evidence_rows=len(rows),
        physical_records=len(puts),
        bdr_sequence=sequence,
    )


def load_evidence_catalog_from_backend(
    backend: AtomicBatchBackend,
) -> EvidenceCore:
    """Restore a fresh EvidenceCore from its durable source catalog.

    Rows are replayed in original insertion order with their original epochs.
    ``EvidenceCore.observe_relation`` consequently restores each namespace's next
    epoch without reaching into private state.
    """
    manifest_raw = _decode_json(backend.get(_ROOT_KEY), _ROOT_KEY)
    if not isinstance(manifest_raw, dict):
        raise ValueError("invalid BDR evidence root manifest")
    if int(manifest_raw.get("schema_version", 0)) != _SCHEMA_VERSION:
        raise ValueError("unsupported BDR evidence snapshot schema version")
    keys_raw = manifest_raw.get("record_keys", [])
    if not isinstance(keys_raw, list):
        raise ValueError("invalid BDR evidence record key list")
    keys = tuple(str(value) for value in keys_raw)
    if len(keys) != len(set(keys)):
        raise ValueError("BDR evidence manifest contains duplicate record key")

    records: list[EvidenceEdge] = []
    seen_ids: set[str] = set()
    for key in keys:
        record = _decode_json(backend.get(key), key)
        if not isinstance(record, dict):
            raise ValueError(f"invalid BDR evidence edge: {key}")
        try:
            evidence_id = str(record["evidence_id"]).strip()
            subject = str(record["subject"]).strip()
            predicate = str(record["predicate"]).strip()
            object_value = str(record["object"]).strip()
            source_text = str(record["source_text"]).strip()
            provenance = str(record["provenance"]).strip()
            origin = str(record["origin"]).strip()
            epoch = int(record["epoch"])
            confidence = float(record["confidence"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid BDR evidence edge fields: {key}") from exc
        if not all((evidence_id, subject, predicate, object_value, source_text, provenance, origin)):
            raise ValueError(f"BDR evidence edge contains blank required field: {key}")
        if evidence_id in seen_ids:
            raise ValueError("BDR evidence catalog contains duplicate evidence_id")
        if epoch < 0:
            raise ValueError("BDR evidence edge epoch must be >= 0")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("BDR evidence edge confidence must be in [0, 1]")
        namespace_raw = record.get("namespace")
        namespace = None if namespace_raw is None else str(namespace_raw)
        records.append(EvidenceEdge(
            subject=subject,
            predicate=predicate,
            object=object_value,
            evidence_id=evidence_id,
            source_text=source_text,
            namespace=namespace,
            epoch=epoch,
            provenance=provenance,
            origin=origin,
            confidence=confidence,
        ))
        seen_ids.add(evidence_id)

    evidence = EvidenceCore()
    for row in records:
        evidence.observe_relation(
            row.subject,
            row.predicate,
            row.object,
            evidence_id=row.evidence_id,
            source_text=row.source_text,
            provenance=row.provenance,
            origin=row.origin,
            confidence=row.confidence,
            namespace=row.namespace,
            epoch=row.epoch,
        )
    return evidence


def save_evidence_catalog_bdr(
    root: str | Path,
    library_path: str | Path,
    evidence: EvidenceCore,
) -> EvidenceBDRStats:
    with CtypesAtomicBDR(root, library_path) as backend:
        return save_evidence_catalog_to_backend(backend, evidence)


def load_evidence_catalog_bdr(
    root: str | Path,
    library_path: str | Path,
) -> tuple[EvidenceCore, EvidenceBDRStats]:
    with CtypesAtomicBDR(root, library_path) as backend:
        evidence = load_evidence_catalog_from_backend(backend)
        return evidence, EvidenceBDRStats(
            evidence_rows=len(evidence.iter_evidence()),
            physical_records=len(evidence.iter_evidence()) + 1,
            bdr_sequence=backend.last_sequence(),
        )
