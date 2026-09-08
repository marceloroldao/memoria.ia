from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .evidence_core import EvidenceCore, EvidenceEdge
from .topological_memory import AddressSpace, TemporalEvent, TemporalEventStore


class EpistemicSource(str, Enum):
    USER_CONFIRMED = "USER_CONFIRMED"
    SENSOR_OBSERVED = "SENSOR_OBSERVED"
    SYSTEM_INFERRED = "SYSTEM_INFERRED"
    LLM_GENERATED = "LLM_GENERATED"
    EXTERNAL_PUBLIC = "EXTERNAL_PUBLIC"
    DERIVED = "DERIVED"


_PROMOTABLE_DEFAULT = frozenset({
    EpistemicSource.USER_CONFIRMED,
    EpistemicSource.SENSOR_OBSERVED,
    EpistemicSource.EXTERNAL_PUBLIC,
})


@dataclass(frozen=True, slots=True)
class EvidenceProjection:
    evidence_id: str
    epistemic_source: EpistemicSource
    promoted: bool
    reason: str
    temporal_event: TemporalEvent | None
    provenance: str
    origin: str
    confidence: float


@dataclass(frozen=True, slots=True)
class EvidenceProjectionBatch:
    projections: tuple[EvidenceProjection, ...]

    @property
    def promoted(self) -> tuple[EvidenceProjection, ...]:
        return tuple(item for item in self.projections if item.promoted)

    @property
    def quarantined(self) -> tuple[EvidenceProjection, ...]:
        return tuple(item for item in self.projections if not item.promoted)


class EpistemicPromotionPolicy:
    """Policy deciding whether an EvidenceCore edge may affect factual temporal state.

    LLM-generated output is intentionally non-promotable by default. The policy
    separates evidence availability/audit from mutation of CURRENT/HISTORY.
    """

    def __init__(
        self,
        *,
        promotable_sources: Iterable[EpistemicSource] = _PROMOTABLE_DEFAULT,
        min_confidence: float = 0.0,
    ) -> None:
        self.promotable_sources = frozenset(promotable_sources)
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        self.min_confidence = float(min_confidence)

    def decide(self, source: EpistemicSource, edge: EvidenceEdge) -> tuple[bool, str]:
        if source is EpistemicSource.LLM_GENERATED:
            return False, "llm-generated evidence requires an explicit external learning gate"
        if source not in self.promotable_sources:
            return False, f"epistemic source {source.value} is not promotable by this policy"
        if edge.confidence < self.min_confidence:
            return False, "evidence confidence is below the promotion threshold"
        return True, "promoted by epistemic policy"


def classify_epistemic_source(edge: EvidenceEdge) -> EpistemicSource:
    """Map existing provenance/origin vocabulary into the explicit epistemic model.

    This is intentionally conservative. Unknown provenance is SYSTEM_INFERRED rather
    than USER_CONFIRMED, so an unfamiliar source cannot silently become factual state.
    """
    tags = {
        edge.provenance.strip().casefold().replace("-", "_").replace(" ", "_"),
        edge.origin.strip().casefold().replace("-", "_").replace(" ", "_"),
    }
    if tags & {"user_confirmed", "user", "conversation", "human", "manual"}:
        return EpistemicSource.USER_CONFIRMED
    if tags & {"sensor_observed", "sensor", "telemetry", "device"}:
        return EpistemicSource.SENSOR_OBSERVED
    if tags & {"llm_generated", "llm", "model", "assistant", "openai", "local_llm"}:
        return EpistemicSource.LLM_GENERATED
    if tags & {"external_public", "public", "web", "external", "curiosity"}:
        return EpistemicSource.EXTERNAL_PUBLIC
    if tags & {"derived", "derivation", "computed"}:
        return EpistemicSource.DERIVED
    return EpistemicSource.SYSTEM_INFERRED


class EvidenceTemporalBridge:
    """Project EvidenceCore history into temporal state without changing EvidenceCore.

    The bridge never deletes or rewrites source evidence. Every edge yields an audit
    projection. Only policy-approved edges create a temporal event.
    """

    def __init__(
        self,
        addresses: AddressSpace,
        store: TemporalEventStore,
        *,
        policy: EpistemicPromotionPolicy | None = None,
    ) -> None:
        if store.addresses is not addresses:
            raise ValueError("store and address space must belong to the same topology")
        self.addresses = addresses
        self.store = store
        self.policy = policy or EpistemicPromotionPolicy()
        self._projected_evidence_ids: set[str] = set()

    def project_edge(self, edge: EvidenceEdge) -> EvidenceProjection:
        if edge.evidence_id in self._projected_evidence_ids:
            return EvidenceProjection(
                evidence_id=edge.evidence_id,
                epistemic_source=classify_epistemic_source(edge),
                promoted=False,
                reason="evidence_id was already projected",
                temporal_event=None,
                provenance=edge.provenance,
                origin=edge.origin,
                confidence=edge.confidence,
            )

        source = classify_epistemic_source(edge)
        allowed, reason = self.policy.decide(source, edge)
        event: TemporalEvent | None = None
        if allowed:
            raw = self.addresses.ingest_text(edge.source_text)
            event = self.store.observe_state(
                edge.subject,
                edge.predicate,
                edge.object,
                source=source.value,
                raw_memory_address=raw.raw_memory_address,
            )
        self._projected_evidence_ids.add(edge.evidence_id)
        return EvidenceProjection(
            evidence_id=edge.evidence_id,
            epistemic_source=source,
            promoted=allowed,
            reason=reason,
            temporal_event=event,
            provenance=edge.provenance,
            origin=edge.origin,
            confidence=edge.confidence,
        )

    def project_history(
        self,
        evidence: EvidenceCore,
        *,
        namespace: str | None = None,
        epoch: int | None = None,
    ) -> EvidenceProjectionBatch:
        edges = evidence.evidence_history(namespace=namespace, epoch=epoch)
        return EvidenceProjectionBatch(tuple(self.project_edge(edge) for edge in edges))
