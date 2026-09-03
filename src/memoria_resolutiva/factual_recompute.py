from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable

from .evidence_core import EvidenceCore
from .incremental_recompute import CombineFn, IncrementalRecomputeGraph
from .memory_provenance import MemoryProvenanceIndex


@dataclass(frozen=True, slots=True)
class RecomputeRevision:
    node_id: Hashable
    old_memory_id: str
    new_memory_id: str
    value: float


class FactualIncrementalRecompute:
    """Incrementally recompute derived factual state after root corrections.

    Numeric values are maintained by IncrementalRecomputeGraph while provenance
    versions describe which current memories support every derived node. Old
    memories are superseded, not deleted, so history/audit remains available.
    """

    def __init__(self, core: EvidenceCore, *, combine: CombineFn | None = None) -> None:
        self.core = core
        self.graph = IncrementalRecomputeGraph(combine=combine)
        self.provenance = MemoryProvenanceIndex(core)
        self.memory_ids: dict[Hashable, str] = {}
        self._revision = 0

    def add_root(
        self,
        node_id: Hashable,
        value: float,
        *,
        memory_id: str,
        source_type: str = "user_assertion",
        namespace: str | None = None,
    ) -> None:
        self.graph.add_root(node_id, value)
        self.memory_ids[node_id] = memory_id
        self.provenance.register(memory_id, source_type=source_type, namespace=namespace)

    def add_derived(
        self,
        node_id: Hashable,
        parents: list[Hashable],
        *,
        memory_id: str,
        combine: CombineFn | None = None,
        namespace: str | None = None,
    ) -> None:
        self.graph.add_derived(node_id, parents, combine=combine)
        parent_memory_ids = tuple(self.memory_ids[parent] for parent in parents)
        self.memory_ids[node_id] = memory_id
        self.provenance.register(
            memory_id,
            source_type="derived_relation",
            parent_memory_ids=parent_memory_ids,
            namespace=namespace,
        )

    def correct_root(
        self,
        node_id: Hashable,
        value: float,
        *,
        new_memory_id: str,
        namespace: str | None = None,
        source_type: str = "user_correction",
    ) -> tuple[RecomputeRevision, ...]:
        current = self.graph.nodes[node_id]
        if current.parents:
            raise ValueError("only root nodes can be corrected directly")

        old_root_memory = self.memory_ids[node_id]
        self.provenance.register(new_memory_id, source_type=source_type, namespace=namespace)
        self.provenance.supersede(old_root_memory, by_memory_id=new_memory_id, namespace=namespace)
        self.memory_ids[node_id] = new_memory_id

        touched = self.graph.update_root_incremental(node_id, value)
        revisions: list[RecomputeRevision] = []
        for affected in touched:
            if affected == node_id:
                continue
            old_memory = self.memory_ids[affected]
            self._revision += 1
            new_memory = f"{old_memory}:recompute:{self._revision}"
            parents = self.graph.nodes[affected].parents
            parent_memory_ids = tuple(self.memory_ids[parent] for parent in parents)
            self.provenance.register(
                new_memory,
                source_type="derived_relation",
                parent_memory_ids=parent_memory_ids,
                namespace=namespace,
            )
            self.provenance.supersede(old_memory, by_memory_id=new_memory, namespace=namespace)
            self.memory_ids[affected] = new_memory
            revisions.append(
                RecomputeRevision(
                    node_id=affected,
                    old_memory_id=old_memory,
                    new_memory_id=new_memory,
                    value=self.graph.nodes[affected].value,
                )
            )
        return tuple(revisions)
