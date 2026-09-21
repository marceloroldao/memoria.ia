from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from .structural_context_observation_v2 import _canonical_context


def _canonical_antecedents(values: Iterable[str]) -> tuple[str, str]:
    materialized = tuple(str(value) for value in values)
    probe = "context:admission:probe"
    if probe in materialized:
        probe = "context:admission:probe:2"
    antecedents, _ = _canonical_context(materialized, probe)
    return antecedents


@dataclass(frozen=True, slots=True)
class StructuralContextAdmissionSnapshot:
    snapshot_id: str
    antecedent_patterns: tuple[str, str]
    active_candidate_ids: tuple[str, ...]
    source_epoch_id: str
    supporting_slice_ids: tuple[str, ...]
    provenance: str = ""


class StructuralContextAdmissionStateMemory:
    """Audit-preserving current admission state for higher-order context evidence.

    Historical StructuralContextObservationMemory remains additive. This state memory
    stores successive evidence-gate snapshots so current recall can distinguish
    formerly supported structure from currently admitted structure without deleting
    history.
    """

    def __init__(self) -> None:
        self._snapshots: list[StructuralContextAdmissionSnapshot] = []
        self._fingerprints: dict[str, StructuralContextAdmissionSnapshot] = {}
        self._latest: dict[
            tuple[str, str],
            StructuralContextAdmissionSnapshot,
        ] = {}
        self._next_id = 1

    @staticmethod
    def _stable_unique(values: Iterable[str]) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = str(raw)
            if not value:
                raise ValueError("admission-state values must be non-empty")
            if value not in seen:
                seen.add(value)
                result.append(value)
        return tuple(result)

    @staticmethod
    def _fingerprint(
        antecedents: tuple[str, str],
        candidate_ids: tuple[str, ...],
        source_epoch_id: str,
        slice_ids: tuple[str, ...],
        provenance: str,
    ) -> str:
        raw = "|".join(
            (
                ",".join(antecedents),
                ",".join(candidate_ids),
                source_epoch_id,
                ",".join(slice_ids),
                provenance,
            )
        )
        return sha256(raw.encode("utf-8")).hexdigest()

    def ingest_snapshot(
        self,
        *,
        antecedent_patterns: Iterable[str],
        active_candidate_ids: Iterable[str],
        source_epoch_id: str,
        supporting_slice_ids: Iterable[str] = (),
        provenance: str = "",
    ) -> StructuralContextAdmissionSnapshot:
        antecedents = _canonical_antecedents(antecedent_patterns)
        epoch = str(source_epoch_id)
        if not epoch:
            raise ValueError("source_epoch_id must be non-empty")
        candidate_ids = tuple(
            sorted(self._stable_unique(active_candidate_ids))
        )
        slice_ids = tuple(
            sorted(self._stable_unique(supporting_slice_ids))
        )
        fingerprint = self._fingerprint(
            antecedents,
            candidate_ids,
            epoch,
            slice_ids,
            str(provenance),
        )
        existing = self._fingerprints.get(fingerprint)
        if existing is not None:
            self._latest[antecedents] = existing
            return existing

        snapshot = StructuralContextAdmissionSnapshot(
            snapshot_id=f"SCAS{self._next_id}",
            antecedent_patterns=antecedents,
            active_candidate_ids=candidate_ids,
            source_epoch_id=epoch,
            supporting_slice_ids=slice_ids,
            provenance=str(provenance),
        )
        self._next_id += 1
        self._snapshots.append(snapshot)
        self._fingerprints[fingerprint] = snapshot
        self._latest[antecedents] = snapshot
        return snapshot

    def current(
        self,
        antecedent_patterns: Iterable[str],
    ) -> StructuralContextAdmissionSnapshot | None:
        return self._latest.get(
            _canonical_antecedents(antecedent_patterns)
        )

    def snapshot(self) -> tuple[StructuralContextAdmissionSnapshot, ...]:
        return tuple(self._snapshots)

    @classmethod
    def restore(
        cls,
        snapshots: tuple[StructuralContextAdmissionSnapshot, ...],
    ) -> "StructuralContextAdmissionStateMemory":
        memory = cls()
        for item in snapshots:
            restored = memory.ingest_snapshot(
                antecedent_patterns=item.antecedent_patterns,
                active_candidate_ids=item.active_candidate_ids,
                source_epoch_id=item.source_epoch_id,
                supporting_slice_ids=item.supporting_slice_ids,
                provenance=item.provenance,
            )
            if restored.snapshot_id != item.snapshot_id:
                raise ValueError("structural context admission snapshot order is invalid")
        return memory
