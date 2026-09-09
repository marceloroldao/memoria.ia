from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .context_compiler import CognitivePacket
from .evidence_core import EvidenceCore, EvidenceEdge


class ResponseClaimStatus(str, Enum):
    SUPPORTED_BY_CONTEXT = "SUPPORTED_BY_CONTEXT"
    CONFLICTS_WITH_CONTEXT = "CONFLICTS_WITH_CONTEXT"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class ResponseClaim:
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class ValidatedResponseClaim:
    claim: ResponseClaim
    status: ResponseClaimStatus
    evidence: EvidenceEdge


@dataclass(frozen=True, slots=True)
class ResponseValidationResult:
    response_id: str
    claims: tuple[ValidatedResponseClaim, ...]

    @property
    def supported(self) -> tuple[ValidatedResponseClaim, ...]:
        return tuple(item for item in self.claims if item.status is ResponseClaimStatus.SUPPORTED_BY_CONTEXT)

    @property
    def conflicts(self) -> tuple[ValidatedResponseClaim, ...]:
        return tuple(item for item in self.claims if item.status is ResponseClaimStatus.CONFLICTS_WITH_CONTEXT)

    @property
    def unverified(self) -> tuple[ValidatedResponseClaim, ...]:
        return tuple(item for item in self.claims if item.status is ResponseClaimStatus.UNVERIFIED)


class ResponseValidator:
    """Post-LLM validation boundary.

    The validator compares structured model claims against the compiled cognitive
    packet and records every claim only as LLM_GENERATED EvidenceCore evidence.
    It never writes TemporalEventStore state and never promotes a model claim to fact.

    Claim extraction itself is intentionally outside this class. A caller may obtain
    structured claims from a model adapter or deterministic parser, but that extraction
    cannot bypass the epistemic barrier implemented here and in EvidenceTemporalBridge.
    """

    def __init__(self, evidence: EvidenceCore) -> None:
        self.evidence = evidence
        self._response_ids: set[str] = set()

    @staticmethod
    def _clean(value: str, field: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"{field} must be non-empty")
        return value

    @staticmethod
    def _claim_status(packet: CognitivePacket, claim: ResponseClaim) -> ResponseClaimStatus:
        subject = claim.subject.strip().casefold()
        predicate = claim.predicate.strip().casefold()
        object_value = claim.object.strip().casefold()

        matching_slot = tuple(
            fact
            for fact in packet.facts
            if fact.subject.strip().casefold() == subject
            and fact.attribute.strip().casefold() == predicate
        )
        if not matching_slot:
            return ResponseClaimStatus.UNVERIFIED
        if any(fact.value.strip().casefold() == object_value for fact in matching_slot):
            return ResponseClaimStatus.SUPPORTED_BY_CONTEXT
        return ResponseClaimStatus.CONFLICTS_WITH_CONTEXT

    def validate(
        self,
        *,
        packet: CognitivePacket,
        response_id: str,
        response_text: str,
        claims: Iterable[ResponseClaim],
        model_id: str,
        namespace: str = "default",
    ) -> ResponseValidationResult:
        response_id = self._clean(response_id, "response_id")
        response_text = self._clean(response_text, "response_text")
        model_id = self._clean(model_id, "model_id")
        namespace = self._clean(namespace, "namespace")
        if response_id in self._response_ids:
            raise ValueError("response_id has already been validated")

        claim_rows = tuple(claims)
        for claim in claim_rows:
            self._clean(claim.subject, "claim.subject")
            self._clean(claim.predicate, "claim.predicate")
            self._clean(claim.object, "claim.object")
            if not 0.0 <= claim.confidence <= 1.0:
                raise ValueError("claim confidence must be in [0, 1]")

        validated: list[ValidatedResponseClaim] = []
        for index, claim in enumerate(claim_rows, start=1):
            status = self._claim_status(packet, claim)
            evidence_id = f"response:{response_id}:claim:{index}"
            edge = self.evidence.observe_relation(
                claim.subject,
                claim.predicate,
                claim.object,
                evidence_id=evidence_id,
                source_text=response_text,
                provenance="LLM_GENERATED",
                origin=(
                    f"response-validator:model={model_id};response={response_id};"
                    f"status={status.value};packet_schema={packet.schema_version}"
                ),
                confidence=float(claim.confidence),
                namespace=namespace,
            )
            validated.append(ValidatedResponseClaim(claim, status, edge))

        self._response_ids.add(response_id)
        return ResponseValidationResult(response_id, tuple(validated))

    def restore_response_ids(self, response_ids: Iterable[str]) -> None:
        restored = tuple(self._clean(value, "response_id") for value in response_ids)
        if len(restored) != len(set(restored)):
            raise ValueError("response validator restore contains duplicate response_id")
        if self._response_ids:
            raise ValueError("response validator must be empty before restore")
        self._response_ids = set(restored)

    def iter_response_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._response_ids))
