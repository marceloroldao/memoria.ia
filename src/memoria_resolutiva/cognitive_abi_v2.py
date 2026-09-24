from __future__ import annotations

from dataclasses import dataclass
import json

from .context_compiler_v2 import CognitiveContextPacketV2
from .epistemic_response_v2 import (
    ClaimConsistencyV2,
    EpistemicClaimCandidateV2,
    EpistemicDecisionV2,
)
from .learning_admission_v2 import LearningAdmissionV2


COGNITIVE_ABI_SCHEMA_V2 = "memoria.ia-cognitive-abi-v2"
COGNITIVE_ABI_VERSION_V2 = 2
_PLANES = {"local", "server"}
_LANGUAGE_PLANES = {"none", "local", "server", "external"}


def _non_empty(value: str, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field} must be non-empty")
    return normalized


@dataclass(frozen=True, slots=True)
class CognitiveOriginDiagnosticsV2:
    execution_plane: str
    memory_plane: str
    language_plane: str
    response_origin: str
    memory_used: bool
    model_used: bool
    external_calls: int
    llm_calls: int

    @classmethod
    def build(
        cls,
        *,
        execution_plane: str,
        memory_plane: str,
        language_plane: str,
        status: str,
        external_calls: int,
        llm_calls: int,
    ) -> "CognitiveOriginDiagnosticsV2":
        execution = str(execution_plane).strip().lower()
        memory = str(memory_plane).strip().lower()
        language = str(language_plane).strip().lower()
        if execution not in _PLANES:
            raise ValueError("execution_plane must be local or server")
        if memory not in _PLANES:
            raise ValueError("memory_plane must be local or server")
        if language not in _LANGUAGE_PLANES:
            raise ValueError("language_plane must be none, local, server or external")
        external = int(external_calls)
        llm = int(llm_calls)
        if external < 0 or llm < 0:
            raise ValueError("call counters must be >= 0")

        memory_used = str(status) != "unresolved"
        model_used = language != "none" or llm > 0
        if not model_used:
            response_origin = f"{memory}-memory" if memory_used else "unresolved"
        elif memory_used and language == memory:
            response_origin = f"{memory}-memory+model"
        elif memory_used:
            response_origin = f"hybrid-{memory}-memory+{language}-model"
        else:
            response_origin = f"{language}-model"

        return cls(
            execution_plane=execution,
            memory_plane=memory,
            language_plane=language,
            response_origin=response_origin,
            memory_used=memory_used,
            model_used=model_used,
            external_calls=external,
            llm_calls=llm,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "execution_plane": self.execution_plane,
            "memory_plane": self.memory_plane,
            "language_plane": self.language_plane,
            "response_origin": self.response_origin,
            "memory_used": self.memory_used,
            "model_used": self.model_used,
            "external_calls": self.external_calls,
            "llm_calls": self.llm_calls,
        }


@dataclass(frozen=True, slots=True)
class CognitiveEpistemicRefsV2:
    claim_id: str | None = None
    validation_status: str | None = None
    decision_id: str | None = None
    decision_action: str | None = None
    admission_id: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "validation_status": self.validation_status,
            "decision_id": self.decision_id,
            "decision_action": self.decision_action,
            "admission_id": self.admission_id,
        }


@dataclass(frozen=True, slots=True)
class CognitiveAbiEnvelopeV2:
    """Stable JSON cognitive boundary shared by local/mobile/server adapters.

    The ABI exposes structural state and lineage only. It does not require raw text
    and does not collapse local/server/model provenance into one opaque answer.
    """

    request_id: str
    hierarchy_id: str
    session_id: str | None
    status: str
    addresses: tuple[int, ...]
    resolved_state: tuple[int, ...]
    competing_states: tuple[int, ...]
    trajectory_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]
    equivalence_witness_ids: tuple[str, ...]
    conflicts: tuple[str, ...]
    source_tier: str
    uncertainty: str
    terminal: bool
    bounded_out: bool
    origin: CognitiveOriginDiagnosticsV2
    epistemic: CognitiveEpistemicRefsV2
    schema: str = COGNITIVE_ABI_SCHEMA_V2
    abi_version: int = COGNITIVE_ABI_VERSION_V2

    @classmethod
    def from_context(
        cls,
        packet: CognitiveContextPacketV2,
        *,
        request_id: str,
        execution_plane: str,
        memory_plane: str,
        session_id: str | None = None,
        language_plane: str = "none",
        external_calls: int | None = None,
        llm_calls: int | None = None,
        claim: EpistemicClaimCandidateV2 | None = None,
        validation: ClaimConsistencyV2 | None = None,
        decision: EpistemicDecisionV2 | None = None,
        admission: LearningAdmissionV2 | None = None,
    ) -> "CognitiveAbiEnvelopeV2":
        rid = _non_empty(request_id, "request_id")
        sid = None if session_id is None else _non_empty(session_id, "session_id")

        if validation is not None and claim is None:
            raise ValueError("validation requires claim")
        if validation is not None and validation.claim_id != claim.claim_id:
            raise ValueError("validation does not belong to claim")
        if decision is not None:
            if claim is None or decision.claim_id != claim.claim_id:
                raise ValueError("decision does not belong to claim")
        if admission is not None:
            if claim is None or admission.claim_id != claim.claim_id:
                raise ValueError("admission does not belong to claim")
            if decision is None or admission.decision_id != decision.decision_id:
                raise ValueError("admission does not belong to decision")

        ext_calls = packet.external_calls if external_calls is None else int(external_calls)
        model_calls = packet.llm_calls if llm_calls is None else int(llm_calls)
        origin = CognitiveOriginDiagnosticsV2.build(
            execution_plane=execution_plane,
            memory_plane=memory_plane,
            language_plane=language_plane,
            status=packet.status,
            external_calls=ext_calls,
            llm_calls=model_calls,
        )
        epistemic = CognitiveEpistemicRefsV2(
            claim_id=None if claim is None else claim.claim_id,
            validation_status=None if validation is None else validation.status,
            decision_id=None if decision is None else decision.decision_id,
            decision_action=None if decision is None else decision.action,
            admission_id=None if admission is None else admission.admission_id,
        )
        return cls(
            request_id=rid,
            hierarchy_id=packet.hierarchy_id,
            session_id=sid,
            status=packet.status,
            addresses=packet.addresses,
            resolved_state=packet.resolved_state,
            competing_states=packet.competing_states,
            trajectory_ids=packet.trajectory_ids,
            provenance_ids=packet.provenance_ids,
            equivalence_witness_ids=packet.equivalence_witness_ids,
            conflicts=packet.conflicts,
            source_tier=packet.source_tier,
            uncertainty=packet.uncertainty,
            terminal=packet.terminal,
            bounded_out=packet.bounded_out,
            origin=origin,
            epistemic=epistemic,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "abi_version": self.abi_version,
            "request_id": self.request_id,
            "hierarchy_id": self.hierarchy_id,
            "session_id": self.session_id,
            "status": self.status,
            "cognitive": {
                "addresses": list(self.addresses),
                "resolved_state": list(self.resolved_state),
                "competing_states": list(self.competing_states),
                "trajectory_ids": list(self.trajectory_ids),
                "provenance_ids": list(self.provenance_ids),
                "equivalence_witness_ids": list(self.equivalence_witness_ids),
                "conflicts": list(self.conflicts),
                "source_tier": self.source_tier,
                "uncertainty": self.uncertainty,
                "terminal": self.terminal,
                "bounded_out": self.bounded_out,
            },
            "origin": self.origin.as_dict(),
            "epistemic": self.epistemic.as_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.as_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, payload: str | bytes) -> "CognitiveAbiEnvelopeV2":
        row = json.loads(payload)
        if not isinstance(row, dict) or row.get("schema") != COGNITIVE_ABI_SCHEMA_V2:
            raise ValueError("unsupported cognitive ABI schema")
        if int(row.get("abi_version", -1)) != COGNITIVE_ABI_VERSION_V2:
            raise ValueError("unsupported cognitive ABI version")
        cognitive = row.get("cognitive")
        origin_row = row.get("origin")
        epistemic_row = row.get("epistemic")
        if not isinstance(cognitive, dict) or not isinstance(origin_row, dict) or not isinstance(epistemic_row, dict):
            raise ValueError("invalid cognitive ABI envelope")

        origin = CognitiveOriginDiagnosticsV2(
            execution_plane=str(origin_row["execution_plane"]),
            memory_plane=str(origin_row["memory_plane"]),
            language_plane=str(origin_row["language_plane"]),
            response_origin=str(origin_row["response_origin"]),
            memory_used=bool(origin_row["memory_used"]),
            model_used=bool(origin_row["model_used"]),
            external_calls=int(origin_row["external_calls"]),
            llm_calls=int(origin_row["llm_calls"]),
        )
        epistemic = CognitiveEpistemicRefsV2(
            claim_id=epistemic_row.get("claim_id"),
            validation_status=epistemic_row.get("validation_status"),
            decision_id=epistemic_row.get("decision_id"),
            decision_action=epistemic_row.get("decision_action"),
            admission_id=epistemic_row.get("admission_id"),
        )
        return cls(
            request_id=_non_empty(row.get("request_id", ""), "request_id"),
            hierarchy_id=_non_empty(row.get("hierarchy_id", ""), "hierarchy_id"),
            session_id=None if row.get("session_id") is None else _non_empty(row["session_id"], "session_id"),
            status=str(row.get("status") or ""),
            addresses=tuple(int(v) for v in cognitive.get("addresses", ())),
            resolved_state=tuple(int(v) for v in cognitive.get("resolved_state", ())),
            competing_states=tuple(int(v) for v in cognitive.get("competing_states", ())),
            trajectory_ids=tuple(str(v) for v in cognitive.get("trajectory_ids", ())),
            provenance_ids=tuple(str(v) for v in cognitive.get("provenance_ids", ())),
            equivalence_witness_ids=tuple(str(v) for v in cognitive.get("equivalence_witness_ids", ())),
            conflicts=tuple(str(v) for v in cognitive.get("conflicts", ())),
            source_tier=str(cognitive.get("source_tier") or ""),
            uncertainty=str(cognitive.get("uncertainty") or ""),
            terminal=bool(cognitive.get("terminal")),
            bounded_out=bool(cognitive.get("bounded_out")),
            origin=origin,
            epistemic=epistemic,
        )
