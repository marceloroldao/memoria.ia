from __future__ import annotations

from dataclasses import asdict

from .memory_provenance import MemoryProvenanceIndex
from .memory_space import memory_space_for_source_type


class MemoryInspectionService:
    """Read-only epistemic inspection view over persisted provenance."""

    def __init__(self, provenance: MemoryProvenanceIndex) -> None:
        self.provenance = provenance

    def inspect(self, memory_id: str, *, namespace: str | None = None) -> dict:
        direct = self.provenance.inspect(memory_id, namespace=namespace)
        active_root = self.provenance.factual_ultimate_source(memory_id, namespace=namespace)
        payload = asdict(direct)
        payload["memory_space"] = memory_space_for_source_type(direct.source_type).value
        payload["factual_active"] = active_root is not None
        payload["active_ultimate_source_memory_id"] = None if active_root is None else active_root.memory_id
        payload["active_ultimate_source_type"] = None if active_root is None else active_root.source_type
        return payload
