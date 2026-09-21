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
    resolution_state: str = "unsupported"
    competing_candidate_ids: tuple[str, ...] = ()


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
        resolution_state: str,
        competing_candidate_ids: tuple[str, ...],
    ) -> str:
        raw = "|".join(
            (
                ",".join(antecedents),
                ",".join(candidate_ids),
                source_epoch_id,
                ",".join(slice_ids),
                provenance,
                resolution_state,
                ",".join(competing_candidate_ids),
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
        resolution_state: str | None = None,
        competing_candidate_ids: Iterable[str] = (),
    ) -> StructuralContextAdmissionSnapshot:
        antecedents = _canonical_antecedents(antecedent_patterns)
        epoch = str(source_epoch_id)
        if not epoch:
            raise ValueError("source_epoch_id must be non-empty")
        candidate_ids = tuple(
            sorted(self._stable_unique(active_candidate_ids))
        )
        competing_ids = tuple(
            sorted(self._stable_unique(competing_candidate_ids))
        )
        if resolution_state is None:
            if len(candidate_ids) == 1:
                state = "resolved"
            elif len(candidate_ids) > 1:
                state = "ambiguous"
                competing_ids = tuple(sorted(set(competing_ids) | set(candidate_ids)))
                candidate_ids = ()
            else:
                state = "unsupported"
        else:
            state = str(resolution_state)
        if state not in {"resolved", "ambiguous", "unsupported"}:
            raise ValueError("resolution_state must be resolved, ambiguous, or unsupported")
        if state == "resolved" and len(candidate_ids) != 1:
            raise ValueError("resolved admission state requires exactly one active candidate")
        if state == "ambiguous" and candidate_ids:
            raise ValueError("ambiguous admission state must not activate a candidate")
        if state == "unsupported" and candidate_ids:
            raise ValueError("unsupported admission state must not activate a candidate")
        if set(candidate_ids) & set(competing_ids):
            raise ValueError("active and competing candidate IDs must be disjoint")
        if state == "ambiguous" and len(competing_ids) < 2:
            raise ValueError("ambiguous admission state requires at least two competing candidates")
        if state != "ambiguous" and competing_ids:
            raise ValueError("competing candidates are only valid for ambiguous state")
        slice_ids = tuple(
            sorted(self._stable_unique(supporting_slice_ids))
        )
        fingerprint = self._fingerprint(
            antecedents,
            candidate_ids,
            epoch,
            slice_ids,
            str(provenance),
            state,
            competing_ids,
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
            resolution_state=state,
            competing_candidate_ids=competing_ids,
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

    def current_contexts(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._latest))

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
                resolution_state=item.resolution_state,
                competing_candidate_ids=item.competing_candidate_ids,
            )
            if restored.snapshot_id != item.snapshot_id:
                raise ValueError("structural context admission snapshot order is invalid")
        return memory
