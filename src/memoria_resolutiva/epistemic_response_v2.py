from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from threading import RLock
from typing import Iterable

from .context_compiler_v2 import CognitiveContextPacketV2


EPISTEMIC_DECISION_FORMAT = "memoria.ia-epistemic-decision-v2"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _opaque_addresses(values: Iterable[int]) -> tuple[int, ...]:
    out: list[int] = []
    for raw in values:
        value = int(raw)
        if value < 0:
            raise ValueError("claim addresses must be >= 0")
        out.append(value)
    return tuple(out)


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
class EpistemicClaimCandidateV2:
    """One externally generated claim before any learning decision.

    The core receives already-addressed assertions. It does not parse language and
    does not treat the generator as an authority.
    """

    claim_id: str
    response_id: str
    claim_index: int
    asserted_addresses: tuple[int, ...]
    provenance_ids: tuple[str, ...]
    surface_ref: str | None = None


def make_claim_candidate_v2(
    *,
    response_id: str,
    claim_index: int,
    asserted_addresses: Iterable[int],
    provenance_ids: Iterable[str] = (),
    surface_ref: str | None = None,
) -> EpistemicClaimCandidateV2:
    response = str(response_id).strip()
    if not response:
        raise ValueError("response_id must be non-empty")
    index = int(claim_index)
    if index < 0:
        raise ValueError("claim_index must be >= 0")
    addresses = _opaque_addresses(asserted_addresses)
    if not addresses:
        raise ValueError("a claim must assert at least one structural address")
    provenance = _stable_strings(provenance_ids)
    surface = None if surface_ref is None else str(surface_ref).strip()
    if surface_ref is not None and not surface:
        raise ValueError("surface_ref must be non-empty when supplied")
    payload = {
        "response_id": response,
        "claim_index": index,
        "asserted_addresses": list(addresses),
        "provenance_ids": list(provenance),
        "surface_ref": surface,
    }
    claim_id = "epistemic-claim:" + hashlib.blake2b(
        _canonical_json(payload), digest_size=20
    ).hexdigest()
    return EpistemicClaimCandidateV2(
        claim_id=claim_id,
        response_id=response,
        claim_index=index,
        asserted_addresses=addresses,
        provenance_ids=provenance,
        surface_ref=surface,
    )


@dataclass(frozen=True, slots=True)
class ClaimConsistencyV2:
    claim_id: str
    status: str
    matched_addresses: tuple[int, ...]
    competing_addresses: tuple[int, ...]
    reason: str
    truth_assessment: bool = False
    memory_mutated: bool = False


class EpistemicResponseValidatorV2:
    """Measure structural consistency with compiled memory, never truth."""

    @staticmethod
    def validate(
        claim: EpistemicClaimCandidateV2,
        context: CognitiveContextPacketV2,
    ) -> ClaimConsistencyV2:
        asserted = set(claim.asserted_addresses)
        resolved = set(context.resolved_state)
        competing = set(context.competing_states)

        matched = tuple(sorted(asserted & resolved))
        contested = tuple(sorted(asserted & competing))

        if context.status == "resolved" and asserted and asserted.issubset(resolved):
            status = "consistent"
            reason = "assertion-contained-in-resolved-state"
        elif contested:
            status = "competing"
            reason = "assertion-overlaps-competing-state"
        elif context.status in {"unresolved", "terminal"}:
            status = "unresolved"
            reason = "context-does-not-provide-resolved-support"
        else:
            status = "unsupported"
            reason = "assertion-not-supported-by-compiled-state"

        return ClaimConsistencyV2(
            claim_id=claim.claim_id,
            status=status,
            matched_addresses=matched,
            competing_addresses=contested,
            reason=reason,
        )


@dataclass(frozen=True, slots=True)
class EpistemicDecisionV2:
    decision_id: str
    sequence: int
    claim_id: str
    action: str
    validator_status: str
    evidence_ids: tuple[str, ...]
    rationale_ref: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "format": EPISTEMIC_DECISION_FORMAT,
            "decision_id": self.decision_id,
            "sequence": self.sequence,
            "claim_id": self.claim_id,
            "action": self.action,
            "validator_status": self.validator_status,
            "evidence_ids": list(self.evidence_ids),
            "rationale_ref": self.rationale_ref,
        }


class EpistemicDecisionLedgerV2:
    """Append-only explicit decisions, separate from claim candidates and memory."""

    _ACTIONS = {"accept", "reject", "defer"}

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._rows: list[EpistemicDecisionV2] = []
        self._by_id: dict[str, EpistemicDecisionV2] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        previous_sequence = -1
        for line_number, line in enumerate(self.path.read_text("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or row.get("format") != EPISTEMIC_DECISION_FORMAT:
                raise ValueError(f"unsupported epistemic decision at line {line_number}")
            item = EpistemicDecisionV2(
                decision_id=str(row.get("decision_id") or ""),
                sequence=int(row.get("sequence", -1)),
                claim_id=str(row.get("claim_id") or ""),
                action=str(row.get("action") or ""),
                validator_status=str(row.get("validator_status") or ""),
                evidence_ids=tuple(str(value) for value in row.get("evidence_ids", ())),
                rationale_ref=None if row.get("rationale_ref") is None else str(row["rationale_ref"]),
            )
            if item.sequence < previous_sequence:
                raise ValueError("epistemic ledger sequence cannot move backward")
            previous_sequence = item.sequence
            self._rows.append(item)
            self._by_id[item.decision_id] = item

    def record(
        self,
        claim: EpistemicClaimCandidateV2,
        validation: ClaimConsistencyV2,
        *,
        sequence: int,
        action: str,
        evidence_ids: Iterable[str] = (),
        rationale_ref: str | None = None,
    ) -> EpistemicDecisionV2:
        if validation.claim_id != claim.claim_id:
            raise ValueError("validation does not belong to claim")
        seq = int(sequence)
        if seq < 0:
            raise ValueError("sequence must be >= 0")
        normalized_action = str(action).strip().lower()
        if normalized_action not in self._ACTIONS:
            raise ValueError("unsupported epistemic decision action")
        evidence = _stable_strings(evidence_ids)
        rationale = None if rationale_ref is None else str(rationale_ref).strip()
        if rationale_ref is not None and not rationale:
            raise ValueError("rationale_ref must be non-empty when supplied")

        payload = {
            "sequence": seq,
            "claim_id": claim.claim_id,
            "action": normalized_action,
            "validator_status": validation.status,
            "evidence_ids": list(evidence),
            "rationale_ref": rationale,
        }
        decision_id = "epistemic-decision:" + hashlib.blake2b(
            _canonical_json(payload), digest_size=20
        ).hexdigest()
        candidate = EpistemicDecisionV2(
            decision_id=decision_id,
            sequence=seq,
            claim_id=claim.claim_id,
            action=normalized_action,
            validator_status=validation.status,
            evidence_ids=evidence,
            rationale_ref=rationale,
        )

        with self._lock:
            existing = self._by_id.get(decision_id)
            if existing is not None:
                return existing
            if self._rows and seq < self._rows[-1].sequence:
                raise ValueError("epistemic ledger sequence cannot move backward")
            line = json.dumps(candidate.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            with self.path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            self._rows.append(candidate)
            self._by_id[decision_id] = candidate
            return candidate

    def snapshot(self) -> tuple[EpistemicDecisionV2, ...]:
        with self._lock:
            return tuple(self._rows)
