from __future__ import annotations

from typing import Protocol

from .conversation_contract import ConversationIngestResult, ConversationResolveResult
from .evidence_core import EvidenceCore
from .repeated_fact_consolidation import RepeatedFactConsolidator


class ConversationBackend(Protocol):
    def ingest(
        self,
        *,
        role: str,
        text: str,
        session_id: str | None = None,
        order: int | None = None,
        timestamp: str | None = None,
        parent_memory_ids: tuple[str, ...] | list[str] = (),
        corrects_memory_ids: tuple[str, ...] | list[str] = (),
    ) -> ConversationIngestResult: ...

    def resolve(self, *, query: str, session_id: str | None = None) -> ConversationResolveResult: ...


class EvidencePersistence(Protocol):
    core: EvidenceCore

    def save(self): ...


class AutoSemanticConsolidationConversationService:
    """Conversation facade that consolidates repeated factual claims after ingest.

    The underlying conversation service remains authoritative for raw turn and
    relation persistence. This facade only scans the shared EvidenceCore after a
    user turn produced relations. A new semantic abstraction is persisted only
    when the repeated-fact policy finds enough independent active factual roots.

    This bridge is intentionally for runtimes that share the Python EvidenceCore.
    Native conversation storage must implement equivalent semantics before it is
    enabled there.
    """

    def __init__(
        self,
        conversation: ConversationBackend,
        evidence: EvidencePersistence,
        *,
        min_independent_roots: int = 2,
    ) -> None:
        if min_independent_roots < 2:
            raise ValueError("min_independent_roots must be >= 2")
        self.conversation = conversation
        self.evidence = evidence
        self.min_independent_roots = min_independent_roots
        self.consolidator = RepeatedFactConsolidator(evidence.core)

    def ingest(
        self,
        *,
        role: str,
        text: str,
        session_id: str | None = None,
        order: int | None = None,
        timestamp: str | None = None,
        parent_memory_ids: tuple[str, ...] | list[str] = (),
        corrects_memory_ids: tuple[str, ...] | list[str] = (),
    ) -> ConversationIngestResult:
        result = self.conversation.ingest(
            role=role,
            text=text,
            session_id=session_id,
            order=order,
            timestamp=timestamp,
            parent_memory_ids=parent_memory_ids,
            corrects_memory_ids=corrects_memory_ids,
        )
        if role != "user" or not result.relations:
            return result

        created = self.consolidator.consolidate_all(
            namespace=session_id,
            min_independent_roots=self.min_independent_roots,
        )
        if created:
            self.evidence.save()
        return result

    def resolve(self, *, query: str, session_id: str | None = None) -> ConversationResolveResult:
        return self.conversation.resolve(query=query, session_id=session_id)
