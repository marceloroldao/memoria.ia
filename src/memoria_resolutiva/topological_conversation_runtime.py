from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .context_compiler import CognitivePacket, ContextCompiler
from .conversation_contract import ConversationService
from .evidence_core import EvidenceCore, EvidenceEdge
from .evidence_temporal_bridge import (
    EpistemicSource,
    EvidenceTemporalBridge,
)
from .learning_gate import EpistemicLearningGate, LearningDecision
from .response_validator import ResponseClaim, ResponseValidationResult, ResponseValidator
from .topological_memory import AddressSpace, TemporalEventStore


@dataclass(frozen=True, slots=True)
class TopologicalConversationResolution:
    packet: CognitivePacket | None
    memory_ids: tuple[str, ...]
    hit: bool
    unresolved: bool


class TopologicalConversationRuntime:
    """Memoria-owned bridge from conversational relations to cognitive state.

    OFF.IA may call this service, but it does not own parsing, epistemic policy,
    topology, temporal state or model-response validation. Text-to-relation
    extraction remains delegated to the existing Memoria.ia ConversationService.

    Direct user assertions are recorded with ``conversation`` provenance, which
    the frozen epistemic bridge classifies as USER_CONFIRMED. Model claims always
    enter through ResponseValidator and are projected only as quarantined
    LLM_GENERATED evidence until an explicit Learning Gate decision creates a
    separate trusted edge.
    """

    def __init__(
        self,
        conversation: ConversationService,
        *,
        evidence: EvidenceCore | None = None,
        addresses: AddressSpace | None = None,
        store: TemporalEventStore | None = None,
        namespace: str = "default",
    ) -> None:
        namespace = namespace.strip()
        if not namespace:
            raise ValueError("namespace must be non-empty")
        self.conversation = conversation
        self.namespace = namespace
        self.evidence = evidence or EvidenceCore()
        if store is not None and addresses is None:
            addresses = store.addresses
        self.addresses = addresses or AddressSpace()
        self.store = store or TemporalEventStore(self.addresses)
        if self.store.addresses is not self.addresses:
            raise ValueError("store and addresses must belong to the same topology")
        self.bridge = EvidenceTemporalBridge(self.addresses, self.store)
        self.gate = EpistemicLearningGate(self.evidence)
        self.validator = ResponseValidator(self.evidence)

    def _existing_evidence(self, evidence_id: str) -> EvidenceEdge | None:
        for edge in self.evidence.iter_evidence():
            if edge.evidence_id == evidence_id:
                return edge
        return None

    def ingest_user(
        self,
        text: str,
        *,
        session_id: str | None = None,
        order: int | None = None,
        timestamp: str | None = None,
    ) -> tuple[str, ...]:
        text = text.strip()
        if not text:
            raise ValueError("text must be non-empty")
        result = self.conversation.ingest(
            role="user",
            text=text,
            session_id=session_id,
            order=order,
            timestamp=timestamp,
        )
        turn_id = result.memory_ids[0] if result.memory_ids else ""
        projected_ids: list[str] = []
        for row in result.relations:
            if not isinstance(row, dict):
                raise ValueError("conversation relation must be a mapping")
            subject = str(row.get("subject") or "").strip()
            predicate = str(row.get("predicate") or "").strip()
            object_value = str(row.get("object") or "").strip()
            evidence_id = str(row.get("memory_id") or "").strip()
            if not all((subject, predicate, object_value, evidence_id)):
                raise ValueError("conversation relation is missing required fields")
            confidence = float(row.get("confidence", 1.0))
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("conversation relation confidence must be in [0, 1]")
            relation_namespace = str(row.get("namespace") or session_id or self.namespace)
            epoch_raw = row.get("epoch")
            epoch = None if epoch_raw is None else int(epoch_raw)

            existing = self._existing_evidence(evidence_id)
            if existing is not None:
                if (
                    existing.subject != subject
                    or existing.predicate != predicate
                    or existing.object != object_value
                    or existing.source_text != text
                    or existing.namespace != relation_namespace
                ):
                    raise ValueError("conversation evidence_id collision")
                self.bridge.project_edge(existing)
                projected_ids.append(existing.evidence_id)
                continue

            edge = self.evidence.observe_relation(
                subject,
                predicate,
                object_value,
                evidence_id=evidence_id,
                source_text=text,
                provenance="conversation",
                origin=f"native-conversation:user;turn={turn_id}",
                confidence=confidence,
                namespace=relation_namespace,
                epoch=epoch,
            )
            projection = self.bridge.project_edge(edge)
            if not projection.promoted:
                raise RuntimeError("direct user assertion was not promoted by epistemic policy")
            projected_ids.append(edge.evidence_id)
        return tuple(projected_ids)

    def resolve(self, question: str) -> TopologicalConversationResolution:
        question = question.strip()
        if not question:
            raise ValueError("question must be non-empty")
        try:
            packet = ContextCompiler(
                self.store,
                projections=self.bridge.iter_projections(),
            ).compile(question)
        except LookupError:
            return TopologicalConversationResolution(None, (), False, True)
        memory_ids = tuple(
            fact.evidence_id
            for fact in packet.facts
            if fact.evidence_id is not None
        )
        return TopologicalConversationResolution(packet, memory_ids, bool(packet.facts or packet.transitions), False)

    def validate_model_response(
        self,
        *,
        packet: CognitivePacket,
        response_id: str,
        response_text: str,
        claims: Iterable[ResponseClaim],
        model_id: str,
        namespace: str | None = None,
    ) -> ResponseValidationResult:
        result = self.validator.validate(
            packet=packet,
            response_id=response_id,
            response_text=response_text,
            claims=claims,
            model_id=model_id,
            namespace=namespace or self.namespace,
        )
        for item in result.claims:
            projection = self.bridge.project_edge(item.evidence)
            if projection.promoted:
                raise RuntimeError("model-generated evidence crossed factual barrier")
        return result

    def decide_learning(
        self,
        *,
        candidate_evidence_id: str,
        decision_id: str,
        accepted: bool,
        validator_source: EpistemicSource,
        validator_id: str,
        reason: str,
    ) -> LearningDecision:
        candidate = self._existing_evidence(candidate_evidence_id)
        if candidate is None:
            raise LookupError("candidate evidence not found")
        decision = self.gate.decide(
            candidate,
            decision_id=decision_id,
            accepted=accepted,
            validator_source=validator_source,
            validator_id=validator_id,
            reason=reason,
        )
        if decision.accepted:
            promoted = self._existing_evidence(decision.promoted_evidence_id or "")
            if promoted is None:
                raise RuntimeError("Learning Gate accepted without creating trusted evidence")
            projection = self.bridge.project_edge(promoted)
            if not projection.promoted:
                raise RuntimeError("trusted Learning Gate evidence was not promoted")
        return decision

    def flush(self) -> None:
        flush = getattr(self.conversation, "flush", None)
        if callable(flush):
            flush()
