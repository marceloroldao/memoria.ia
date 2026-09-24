from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from threading import RLock

from .epistemic_response_v2 import EpistemicClaimCandidateV2, EpistemicDecisionV2
from .structural_observation import StructuralObservationStore


EPISTEMIC_ADMISSION_FORMAT = "memoria.ia-epistemic-admission-v2"
EPISTEMIC_BINDING_FORMAT = "memoria.ia-epistemic-observation-binding-v2"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class EpistemicEvidenceAdmissionV2:
    admission_id: str
    sequence: int
    claim_id: str
    decision_id: str
    validator_status: str
    asserted_addresses: tuple[int, ...]
    decision_evidence_ids: tuple[str, ...]
    memory_observation_created: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "format": EPISTEMIC_ADMISSION_FORMAT,
            "admission_id": self.admission_id,
            "sequence": self.sequence,
            "claim_id": self.claim_id,
            "decision_id": self.decision_id,
            "validator_status": self.validator_status,
            "asserted_addresses": list(self.asserted_addresses),
            "decision_evidence_ids": list(self.decision_evidence_ids),
            "memory_observation_created": self.memory_observation_created,
        }


@dataclass(frozen=True, slots=True)
class EpistemicObservationBindingV2:
    binding_id: str
    admission_id: str
    observation_id: str
    asserted_addresses: tuple[int, ...]
    observation_trail: tuple[int, ...]
    memory_observation_created: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "format": EPISTEMIC_BINDING_FORMAT,
            "binding_id": self.binding_id,
            "admission_id": self.admission_id,
            "observation_id": self.observation_id,
            "asserted_addresses": list(self.asserted_addresses),
            "observation_trail": list(self.observation_trail),
            "memory_observation_created": self.memory_observation_created,
        }


class EpistemicEvidenceAdmissionLedgerV2:
    """Explicit admission without converting a model claim into an observation.

    An accepted decision may authorize consideration of the claim, but this ledger
    never writes StructuralObservation rows or trajectories. A real observation
    must exist independently before it can be bound to an admission.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._admissions: list[EpistemicEvidenceAdmissionV2] = []
        self._bindings: list[EpistemicObservationBindingV2] = []
        self._admission_by_id: dict[str, EpistemicEvidenceAdmissionV2] = {}
        self._binding_by_id: dict[str, EpistemicObservationBindingV2] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        for line_number, line in enumerate(self.path.read_text("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"invalid epistemic admission row at line {line_number}")
            fmt = row.get("format")
            if fmt == EPISTEMIC_ADMISSION_FORMAT:
                item = EpistemicEvidenceAdmissionV2(
                    admission_id=str(row.get("admission_id") or ""),
                    sequence=int(row.get("sequence", -1)),
                    claim_id=str(row.get("claim_id") or ""),
                    decision_id=str(row.get("decision_id") or ""),
                    validator_status=str(row.get("validator_status") or ""),
                    asserted_addresses=tuple(int(value) for value in row.get("asserted_addresses", ())),
                    decision_evidence_ids=tuple(str(value) for value in row.get("decision_evidence_ids", ())),
                    memory_observation_created=bool(row.get("memory_observation_created", False)),
                )
                self._admissions.append(item)
                self._admission_by_id[item.admission_id] = item
            elif fmt == EPISTEMIC_BINDING_FORMAT:
                item = EpistemicObservationBindingV2(
                    binding_id=str(row.get("binding_id") or ""),
                    admission_id=str(row.get("admission_id") or ""),
                    observation_id=str(row.get("observation_id") or ""),
                    asserted_addresses=tuple(int(value) for value in row.get("asserted_addresses", ())),
                    observation_trail=tuple(int(value) for value in row.get("observation_trail", ())),
                    memory_observation_created=bool(row.get("memory_observation_created", False)),
                )
                self._bindings.append(item)
                self._binding_by_id[item.binding_id] = item
            else:
                raise ValueError(f"unsupported epistemic admission format at line {line_number}")

    def _append(self, row: dict[str, object]) -> None:
        line = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def admit(
        self,
        claim: EpistemicClaimCandidateV2,
        decision: EpistemicDecisionV2,
    ) -> EpistemicEvidenceAdmissionV2:
        if decision.claim_id != claim.claim_id:
            raise ValueError("decision does not belong to claim")
        if decision.action != "accept":
            raise ValueError("only an explicit accept decision may create an admission")
        payload = {
            "sequence": decision.sequence,
            "claim_id": claim.claim_id,
            "decision_id": decision.decision_id,
            "validator_status": decision.validator_status,
            "asserted_addresses": list(claim.asserted_addresses),
            "decision_evidence_ids": list(decision.evidence_ids),
        }
        admission_id = "epistemic-admission:" + hashlib.blake2b(
            _canonical_json(payload), digest_size=20
        ).hexdigest()
        item = EpistemicEvidenceAdmissionV2(
            admission_id=admission_id,
            sequence=decision.sequence,
            claim_id=claim.claim_id,
            decision_id=decision.decision_id,
            validator_status=decision.validator_status,
            asserted_addresses=claim.asserted_addresses,
            decision_evidence_ids=decision.evidence_ids,
        )
        with self._lock:
            existing = self._admission_by_id.get(admission_id)
            if existing is not None:
                return existing
            self._append(item.as_dict())
            self._admissions.append(item)
            self._admission_by_id[admission_id] = item
            return item

    def bind_observation(
        self,
        admission: EpistemicEvidenceAdmissionV2,
        observations: StructuralObservationStore,
        observation_id: str,
    ) -> EpistemicObservationBindingV2:
        observed = observations.get(str(observation_id))
        trail = tuple(int(value) for value in observed["event"]["trail"])
        if trail != admission.asserted_addresses:
            raise ValueError("observation trail does not match admitted claim addresses")
        payload = {
            "admission_id": admission.admission_id,
            "observation_id": str(observation_id),
            "asserted_addresses": list(admission.asserted_addresses),
            "observation_trail": list(trail),
        }
        binding_id = "epistemic-binding:" + hashlib.blake2b(
            _canonical_json(payload), digest_size=20
        ).hexdigest()
        item = EpistemicObservationBindingV2(
            binding_id=binding_id,
            admission_id=admission.admission_id,
            observation_id=str(observation_id),
            asserted_addresses=admission.asserted_addresses,
            observation_trail=trail,
        )
        with self._lock:
            existing = self._binding_by_id.get(binding_id)
            if existing is not None:
                return existing
            self._append(item.as_dict())
            self._bindings.append(item)
            self._binding_by_id[binding_id] = item
            return item

    def admissions(self) -> tuple[EpistemicEvidenceAdmissionV2, ...]:
        with self._lock:
            return tuple(self._admissions)

    def bindings(self) -> tuple[EpistemicObservationBindingV2, ...]:
        with self._lock:
            return tuple(self._bindings)
