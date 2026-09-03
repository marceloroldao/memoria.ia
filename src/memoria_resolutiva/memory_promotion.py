from __future__ import annotations

from dataclasses import dataclass

from .memory_provenance import MemoryProvenance, MemoryProvenanceIndex
from .memory_space import MemorySpace, memory_space_for_source_type


@dataclass(frozen=True, slots=True)
class MemoryPromotion:
    """Result of explicitly validating a generative memory candidate.

    Promotion never mutates the generative record. It creates a new factual
    memory whose authority comes from independent validating evidence and keeps
    lineage to both the candidate and validator for auditability.
    """

    candidate_memory_id: str
    validating_memory_id: str
    promoted_memory_id: str
    source_type: str
    memory_space: MemorySpace


class MemoryPromotionService:
    """Conservative bridge from generative candidates into factual memory."""

    def __init__(self, provenance: MemoryProvenanceIndex) -> None:
        self.provenance = provenance

    def promote(
        self,
        candidate_memory_id: str,
        *,
        validating_memory_id: str,
        promoted_memory_id: str,
        created_order: int | None = None,
        created_time: str | None = None,
        namespace: str | None = None,
    ) -> MemoryPromotion:
        candidate = self.provenance.inspect(candidate_memory_id, namespace=namespace)
        if memory_space_for_source_type(candidate.source_type) is not MemorySpace.GENERATIVE:
            raise ValueError("candidate must belong to generative memory space")

        validator = self.provenance.factual_ultimate_source(validating_memory_id, namespace=namespace)
        if validator is None:
            raise ValueError("promotion requires independent active factual validation")

        # The promoted memory inherits the validator's factual source class rather
        # than the candidate's generative authority. The candidate is preserved as
        # lineage only; it is never converted in place.
        promoted = self.provenance.register(
            promoted_memory_id,
            source_type=validator.source_type,
            parent_memory_ids=(validating_memory_id,),
            created_order=created_order,
            created_time=created_time,
            namespace=namespace,
        )
        return MemoryPromotion(
            candidate_memory_id=candidate_memory_id,
            validating_memory_id=validating_memory_id,
            promoted_memory_id=promoted.memory_id,
            source_type=promoted.source_type,
            memory_space=memory_space_for_source_type(promoted.source_type),
        )

    def inspect_candidate(self, memory_id: str, *, namespace: str | None = None) -> MemoryProvenance:
        """Expose the unchanged source record for audit/history UIs."""

        return self.provenance.inspect(memory_id, namespace=namespace)
