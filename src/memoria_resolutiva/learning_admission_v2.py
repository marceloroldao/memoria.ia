from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from threading import RLock
from typing import Iterable

from .epistemic_response_v2 import EpistemicClaimCandidateV2, EpistemicDecisionV2
from .structural_trajectory_v2 import StructuralTrajectory, StructuralTrajectoryIndex


LEARNING_ADMISSION_FORMAT = "memoria.ia-learning-admission-v2"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _stable_strings(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = str(raw).strip()
        if not value:
            raise ValueError("identifiers must be non-empty")
        if value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class LearningAdmissionV2:
    admission_id: str
    sequence: int
    hierarchy_id: str
    claim_id: str
    decision_id: str
    asserted_addresses: tuple[int, ...]
    evidence_ids: tuple[str, ...]
    validator_status: str

    def as_dict(self) -> dict[str, object]:
        return {
            "format": LEARNING_ADMISSION_FORMAT,
            "admission_id": self.admission_id,
            "sequence": self.sequence,
            "hierarchy_id": self.hierarchy_id,
            "claim_id": self.claim_id,
            "decision_id": self.decision_id,
            "asserted_addresses": list(self.asserted_addresses),
            "evidence_ids": list(self.evidence_ids),
            "validator_status": self.validator_status,
        }


class LearningAdmissionJournalV2:
    """Durable admissions between epistemic decisions and trajectory evidence.

    An admission is evidence, not a truth verdict. It never rewrites the original
    model/external claim or its decision record.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._rows: list[LearningAdmissionV2] = []
        self._by_id: dict[str, LearningAdmissionV2] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        previous_sequence = -1
        for line_number, line in enumerate(self.path.read_text("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or row.get("format") != LEARNING_ADMISSION_FORMAT:
                raise ValueError(f"unsupported learning admission at line {line_number}")
            item = LearningAdmissionV2(
                admission_id=str(row.get("admission_id") or ""),
                sequence=int(row.get("sequence", -1)),
                hierarchy_id=str(row.get("hierarchy_id") or ""),
                claim_id=str(row.get("claim_id") or ""),
                decision_id=str(row.get("decision_id") or ""),
                asserted_addresses=tuple(int(v) for v in row.get("asserted_addresses", ())),
                evidence_ids=tuple(str(v) for v in row.get("evidence_ids", ())),
                validator_status=str(row.get("validator_status") or ""),
            )
            if item.sequence < previous_sequence:
                raise ValueError("learning admission sequence cannot move backward")
            previous_sequence = item.sequence
            self._rows.append(item)
            self._by_id[item.admission_id] = item

    def append(
        self,
        claim: EpistemicClaimCandidateV2,
        decision: EpistemicDecisionV2,
        *,
        hierarchy_id: str,
        sequence: int,
    ) -> LearningAdmissionV2:
        if decision.claim_id != claim.claim_id:
            raise ValueError("decision does not belong to claim")
        if decision.action != "accept":
            raise ValueError("only explicit accept decisions may be admitted")
        evidence_ids = _stable_strings(decision.evidence_ids)
        if not evidence_ids:
            raise ValueError("learning admission requires explicit evidence_ids")
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        seq = int(sequence)
        if seq < 0:
            raise ValueError("sequence must be >= 0")

        payload = {
            "sequence": seq,
            "hierarchy_id": hierarchy,
            "claim_id": claim.claim_id,
            "decision_id": decision.decision_id,
            "asserted_addresses": list(claim.asserted_addresses),
            "evidence_ids": list(evidence_ids),
            "validator_status": decision.validator_status,
        }
        admission_id = "learning-admission:" + hashlib.blake2b(
            _canonical_json(payload), digest_size=20
        ).hexdigest()
        candidate = LearningAdmissionV2(
            admission_id=admission_id,
            sequence=seq,
            hierarchy_id=hierarchy,
            claim_id=claim.claim_id,
            decision_id=decision.decision_id,
            asserted_addresses=claim.asserted_addresses,
            evidence_ids=evidence_ids,
            validator_status=decision.validator_status,
        )

        with self._lock:
            existing = self._by_id.get(admission_id)
            if existing is not None:
                return existing
            if self._rows and seq < self._rows[-1].sequence:
                raise ValueError("learning admission sequence cannot move backward")
            line = json.dumps(candidate.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            with self.path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            self._rows.append(candidate)
            self._by_id[admission_id] = candidate
            return candidate

    def snapshot(self) -> tuple[LearningAdmissionV2, ...]:
        with self._lock:
            return tuple(self._rows)


class LearningAdmissionAdapterV2:
    """Project explicit admissions into structural trajectory evidence."""

    def __init__(
        self,
        journal: LearningAdmissionJournalV2,
        trajectories: StructuralTrajectoryIndex,
    ) -> None:
        self.journal = journal
        self.trajectories = trajectories

    @staticmethod
    def _source_id(item: LearningAdmissionV2) -> str:
        return "epistemic-admission:" + item.decision_id

    def apply(self, item: LearningAdmissionV2) -> StructuralTrajectory:
        return self.trajectories.ingest_addresses(
            item.asserted_addresses,
            hierarchy_id=item.hierarchy_id,
            source_id=self._source_id(item),
            sequence=item.sequence,
            observation_id=item.admission_id,
        )

    def admit(
        self,
        claim: EpistemicClaimCandidateV2,
        decision: EpistemicDecisionV2,
        *,
        hierarchy_id: str,
        sequence: int,
    ) -> tuple[LearningAdmissionV2, StructuralTrajectory]:
        item = self.journal.append(
            claim,
            decision,
            hierarchy_id=hierarchy_id,
            sequence=sequence,
        )
        return item, self.apply(item)

    def replay(self) -> int:
        before = self.trajectories.count
        for item in self.journal.snapshot():
            self.apply(item)
        return self.trajectories.count - before
