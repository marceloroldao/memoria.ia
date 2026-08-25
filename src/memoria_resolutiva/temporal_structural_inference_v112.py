from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .structural_inference_v111 import (
    StructuralEdgeV111,
    StructuralInferenceMemoryV111,
    StructuralInferenceResultV111,
    StructuralPathV111,
)


_SINGLE_VALUE_PREDICATES = {"has_voltage", "belongs_to", "located_at"}


@dataclass(frozen=True, slots=True)
class TemporalStructuralEdgeV112(StructuralEdgeV111):
    epoch: int = 0


@dataclass(frozen=True, slots=True)
class StructuralConflictV112:
    subject: str
    predicate: str
    epoch: int
    values: tuple[str, ...]
    memory_ids: tuple[str, ...]
    namespace: str | None


class TemporalStructuralInferenceMemoryV112(StructuralInferenceMemoryV111):
    """v1.11 structural inference plus temporal state and conflict abstention.

    Observations are append-only. For each (subject, predicate, namespace) slot,
    only evidence from the latest epoch visible to the query is active. A later
    epoch therefore represents a state transition rather than a contradiction.

    Some predicates are single-valued by contract (currently has_voltage,
    belongs_to and located_at). If the latest visible epoch contains multiple
    different values for one of these slots, the slot is conflicted and every
    edge from that slot is withheld from structural traversal. Multi-valued
    predicates such as powers and measures remain usable when several values are
    observed in the same epoch.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._temporal_edges: list[TemporalStructuralEdgeV112] = []
        self._next_epoch_by_namespace: dict[str | None, int] = defaultdict(int)

    def observe(
        self,
        text: str,
        *,
        provenance: str = "conversation",
        namespace: str | None = None,
        epoch: int | None = None,
    ):
        if epoch is None:
            epoch = self._next_epoch_by_namespace[namespace]
            self._next_epoch_by_namespace[namespace] += 1
        elif epoch < 0:
            raise ValueError("epoch must be >= 0")
        else:
            self._next_epoch_by_namespace[namespace] = max(
                self._next_epoch_by_namespace[namespace], epoch + 1
            )

        observed = super().observe(text, provenance=provenance, namespace=namespace)
        frame = self._frame_for_memory(observed.memory_id, namespace=namespace)
        if frame is not None:
            for relation in frame.relations:
                self._temporal_edges.append(
                    TemporalStructuralEdgeV112(
                        subject=relation.subject,
                        predicate=relation.predicate,
                        object=relation.object,
                        memory_id=frame.memory_id,
                        source_text=frame.source_text,
                        namespace=namespace,
                        epoch=epoch,
                    )
                )
        return observed

    def _frame_for_memory(self, memory_id: str, *, namespace: str | None):
        for frame in self._frames(namespace=namespace):
            if frame.memory_id == memory_id:
                return frame
        return None

    def _visible_edges(
        self,
        *,
        namespace: str | None,
        epoch: int | None,
    ) -> tuple[TemporalStructuralEdgeV112, ...]:
        scoped = [edge for edge in self._temporal_edges if edge.namespace == namespace]
        if epoch is not None:
            scoped = [edge for edge in scoped if edge.epoch <= epoch]
        return tuple(scoped)

    def conflicts(
        self,
        *,
        namespace: str | None = None,
        epoch: int | None = None,
    ) -> tuple[StructuralConflictV112, ...]:
        grouped: dict[tuple[str, str], list[TemporalStructuralEdgeV112]] = defaultdict(list)
        for edge in self._visible_edges(namespace=namespace, epoch=epoch):
            grouped[(self._key(edge.subject), edge.predicate)].append(edge)

        out: list[StructuralConflictV112] = []
        for (_subject_key, predicate), slot in grouped.items():
            if predicate not in _SINGLE_VALUE_PREDICATES:
                continue
            latest_epoch = max(edge.epoch for edge in slot)
            active = [edge for edge in slot if edge.epoch == latest_epoch]
            values = sorted({self._key(edge.object): edge.object for edge in active}.values(), key=str.casefold)
            if len(values) <= 1:
                continue
            out.append(
                StructuralConflictV112(
                    subject=active[0].subject,
                    predicate=predicate,
                    epoch=latest_epoch,
                    values=tuple(values),
                    memory_ids=tuple(sorted({edge.memory_id for edge in active})),
                    namespace=namespace,
                )
            )
        return tuple(sorted(out, key=lambda c: (self._key(c.subject), c.predicate, c.epoch)))

    def edges(
        self,
        *,
        namespace: str | None = None,
        epoch: int | None = None,
    ) -> tuple[TemporalStructuralEdgeV112, ...]:
        visible = self._visible_edges(namespace=namespace, epoch=epoch)
        grouped: dict[tuple[str, str], list[TemporalStructuralEdgeV112]] = defaultdict(list)
        for edge in visible:
            grouped[(self._key(edge.subject), edge.predicate)].append(edge)

        conflicted = {
            (self._key(conflict.subject), conflict.predicate, conflict.epoch)
            for conflict in self.conflicts(namespace=namespace, epoch=epoch)
        }
        out: list[TemporalStructuralEdgeV112] = []
        seen: set[tuple[str, str, str, str, int]] = set()
        for (subject_key, predicate), slot in grouped.items():
            latest_epoch = max(edge.epoch for edge in slot)
            for edge in slot:
                if edge.epoch != latest_epoch:
                    continue
                if (subject_key, predicate, latest_epoch) in conflicted:
                    continue
                key = (
                    subject_key,
                    predicate,
                    self._key(edge.object),
                    edge.memory_id,
                    edge.epoch,
                )
                if key in seen:
                    continue
                seen.add(key)
                out.append(edge)
        return tuple(out)

    def infer_path(
        self,
        source: str,
        target: str,
        *,
        max_hops: int = 3,
        max_paths: int = 5,
        namespace: str | None = None,
        epoch: int | None = None,
    ) -> StructuralInferenceResultV111:
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        if max_paths < 1:
            raise ValueError("max_paths must be >= 1")

        source_key = self._key(source)
        target_key = self._key(target)
        adjacency: dict[str, list[TemporalStructuralEdgeV112]] = defaultdict(list)
        canonical: dict[str, str] = {}
        for edge in self.edges(namespace=namespace, epoch=epoch):
            s, o = self._key(edge.subject), self._key(edge.object)
            adjacency[s].append(edge)
            canonical.setdefault(s, edge.subject)
            canonical.setdefault(o, edge.object)

        queue: list[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = [
            (source_key, (source,), (), (), ())
        ]
        paths: list[StructuralPathV111] = []
        while queue and len(paths) < max_paths:
            node, nodes, predicates, memory_ids, source_texts = queue.pop(0)
            if len(predicates) >= max_hops:
                continue
            for edge in sorted(
                adjacency.get(node, ()),
                key=lambda e: (self._key(e.object), e.predicate, e.epoch, e.memory_id),
            ):
                nxt = self._key(edge.object)
                if nxt in {self._key(item) for item in nodes}:
                    continue
                new_nodes = (*nodes, canonical.get(nxt, edge.object))
                new_predicates = (*predicates, edge.predicate)
                new_memory_ids = (*memory_ids, edge.memory_id)
                new_source_texts = (*source_texts, edge.source_text)
                if nxt == target_key:
                    paths.append(
                        StructuralPathV111(
                            nodes=new_nodes,
                            predicates=new_predicates,
                            memory_ids=new_memory_ids,
                            source_texts=new_source_texts,
                            hops=len(new_predicates),
                        )
                    )
                    if len(paths) >= max_paths:
                        break
                else:
                    queue.append((nxt, new_nodes, new_predicates, new_memory_ids, new_source_texts))

        return StructuralInferenceResultV111(
            source=source,
            target=target,
            paths=tuple(paths),
            inferred=bool(paths),
            unsupported_claims=0,
        )
