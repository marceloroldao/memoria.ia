from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from .source_reliability import SourceReliabilityMemory

_SINGLE_VALUE_PREDICATES = frozenset({"has_voltage", "belongs_to", "located_at"})


@dataclass(frozen=True, slots=True)
class EvidenceEdge:
    subject: str
    predicate: str
    object: str
    evidence_id: str
    source_text: str
    namespace: str | None
    epoch: int
    provenance: str
    origin: str
    confidence: float


@dataclass(frozen=True, slots=True)
class EvidenceConflict:
    subject: str
    predicate: str
    namespace: str | None
    epoch: int
    values: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidencePath:
    nodes: tuple[str, ...]
    predicates: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_texts: tuple[str, ...]
    origins_by_edge: tuple[tuple[str, ...], ...]
    confidences: tuple[float, ...]
    reliabilities: tuple[float, ...]
    hops: int
    confidence: float
    independent_origin_floor: int
    reliability_floor: float
    kind: str = "evidence_path"
    synthesized_claims: int = 0


@dataclass(frozen=True, slots=True)
class EvidenceInferenceResult:
    source: str
    target: str
    paths: tuple[EvidencePath, ...]
    inferred: bool
    unsupported_claims: int = 0


@dataclass(frozen=True, slots=True)
class ReliabilityAdjudication:
    resolution_id: str
    origin: str
    confirmed: bool
    adjudicator_origins: tuple[str, ...]
    weight: float


class EvidenceCore:
    """Stable v1 candidate evidence graph.

    The core stores explicit source-backed relations and performs conservative
    traversal. It never parses natural language and never synthesizes predicates;
    parsing/routing are adapters above this boundary.
    """

    def __init__(self) -> None:
        self._edges: list[EvidenceEdge] = []
        self._next_epoch: dict[str | None, int] = defaultdict(int)
        self._reliability = SourceReliabilityMemory()
        self._adjudications: list[ReliabilityAdjudication] = []
        self._resolution_ids: set[str] = set()
        self._adjudication_graph: dict[str, set[str]] = defaultdict(set)

    @staticmethod
    def _key(value: str) -> str:
        return " ".join(value.strip().split()).casefold()

    @staticmethod
    def _clean(value: str, field: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"{field} must be non-empty")
        return value

    def observe_relation(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        evidence_id: str,
        source_text: str,
        provenance: str = "conversation",
        origin: str | None = None,
        confidence: float = 1.0,
        namespace: str | None = None,
        epoch: int | None = None,
    ) -> EvidenceEdge:
        subject = self._clean(subject, "subject")
        predicate = self._clean(predicate, "predicate")
        object = self._clean(object, "object")
        evidence_id = self._clean(evidence_id, "evidence_id")
        source_text = self._clean(source_text, "source_text")
        provenance = self._clean(provenance, "provenance")
        origin = provenance if origin is None else self._clean(origin, "origin")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if epoch is None:
            epoch = self._next_epoch[namespace]
            self._next_epoch[namespace] += 1
        elif epoch < 0:
            raise ValueError("epoch must be >= 0")
        else:
            self._next_epoch[namespace] = max(self._next_epoch[namespace], epoch + 1)
        edge = EvidenceEdge(
            subject, predicate, object, evidence_id, source_text, namespace,
            epoch, provenance, origin, float(confidence)
        )
        self._edges.append(edge)
        return edge

    def _visible(self, namespace: str | None, epoch: int | None) -> tuple[EvidenceEdge, ...]:
        rows = [e for e in self._edges if e.namespace == namespace]
        if epoch is not None:
            rows = [e for e in rows if e.epoch <= epoch]
        return tuple(rows)

    def conflicts(self, *, namespace: str | None = None, epoch: int | None = None) -> tuple[EvidenceConflict, ...]:
        grouped: dict[tuple[str, str], list[EvidenceEdge]] = defaultdict(list)
        for edge in self._visible(namespace, epoch):
            grouped[(self._key(edge.subject), edge.predicate)].append(edge)
        out: list[EvidenceConflict] = []
        for (_subject, predicate), slot in grouped.items():
            if predicate not in _SINGLE_VALUE_PREDICATES:
                continue
            latest = max(e.epoch for e in slot)
            active = [e for e in slot if e.epoch == latest]
            values = {self._key(e.object): e.object for e in active}
            if len(values) > 1:
                out.append(EvidenceConflict(
                    active[0].subject, predicate, namespace, latest,
                    tuple(sorted(values.values(), key=str.casefold)),
                    tuple(sorted({e.evidence_id for e in active})),
                ))
        return tuple(sorted(out, key=lambda c: (self._key(c.subject), c.predicate, c.epoch)))

    def active_edges(self, *, namespace: str | None = None, epoch: int | None = None) -> tuple[EvidenceEdge, ...]:
        visible = self._visible(namespace, epoch)
        grouped: dict[tuple[str, str], list[EvidenceEdge]] = defaultdict(list)
        for edge in visible:
            grouped[(self._key(edge.subject), edge.predicate)].append(edge)
        conflicted = {(self._key(c.subject), c.predicate, c.epoch) for c in self.conflicts(namespace=namespace, epoch=epoch)}
        out: list[EvidenceEdge] = []
        for (subject_key, predicate), slot in grouped.items():
            latest = max(e.epoch for e in slot)
            if (subject_key, predicate, latest) in conflicted:
                continue
            out.extend(e for e in slot if e.epoch == latest)
        return tuple(out)

    def origin_reliability(self, origin: str, *, metric: str = "posterior") -> float:
        origin = self._clean(origin, "origin")
        if metric == "posterior":
            return self._reliability.reliability(origin)
        if metric == "wilson":
            return self._reliability.wilson_lower(origin)
        raise ValueError("metric must be 'posterior' or 'wilson'")

    @staticmethod
    def _path_exists(graph: dict[str, set[str]], source: str, target: str) -> bool:
        if source == target:
            return True
        queue = deque([source])
        seen = {source}
        while queue:
            node = queue.popleft()
            for nxt in graph.get(node, ()):
                if nxt == target:
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return False

    def adjudicate_origin(
        self,
        origin: str,
        *,
        resolution_id: str,
        confirmed: bool,
        adjudicator_origins: tuple[str, ...] | list[str],
        weight: float = 1.0,
    ) -> ReliabilityAdjudication:
        origin = self._clean(origin, "origin")
        resolution_id = self._clean(resolution_id, "resolution_id")
        if resolution_id in self._resolution_ids:
            raise ValueError("resolution_id has already been applied")
        if weight <= 0:
            raise ValueError("weight must be positive")
        adjudicators = tuple(sorted({self._clean(a, "adjudicator_origin") for a in adjudicator_origins}))
        if not adjudicators:
            raise ValueError("at least one independent adjudicator origin is required")
        if origin in adjudicators:
            raise ValueError("an origin cannot adjudicate its own reliability")
        for adjudicator in adjudicators:
            if self._path_exists(self._adjudication_graph, origin, adjudicator):
                raise ValueError("adjudication would create a reliability cycle")
        if confirmed:
            self._reliability.confirm(origin, weight)
        else:
            self._reliability.contradict(origin, weight)
        record = ReliabilityAdjudication(resolution_id, origin, bool(confirmed), adjudicators, float(weight))
        self._resolution_ids.add(resolution_id)
        self._adjudications.append(record)
        for adjudicator in adjudicators:
            self._adjudication_graph[adjudicator].add(origin)
        return record

    def infer_path(
        self,
        source: str,
        target: str,
        *,
        max_hops: int = 3,
        max_paths: int = 5,
        namespace: str | None = None,
        epoch: int | None = None,
        min_confidence: float = 0.0,
        min_independent_origins: int = 1,
        min_origin_reliability: float | None = None,
        reliability_metric: str = "posterior",
    ) -> EvidenceInferenceResult:
        if max_hops < 1 or max_paths < 1:
            raise ValueError("max_hops and max_paths must be >= 1")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        if min_independent_origins < 1:
            raise ValueError("min_independent_origins must be >= 1")
        if min_origin_reliability is not None and not 0.0 <= min_origin_reliability <= 1.0:
            raise ValueError("min_origin_reliability must be in [0, 1]")

        logical: dict[tuple[str, str, str], list[EvidenceEdge]] = defaultdict(list)
        for edge in self.active_edges(namespace=namespace, epoch=epoch):
            logical[(self._key(edge.subject), edge.predicate, self._key(edge.object))].append(edge)

        adjacency: dict[str, list[tuple[EvidenceEdge, tuple[str, ...], float, float]]] = defaultdict(list)
        canonical: dict[str, str] = {}
        for (s, _predicate, o), rows in logical.items():
            by_origin: dict[str, list[EvidenceEdge]] = defaultdict(list)
            for row in rows:
                by_origin[row.origin].append(row)
            accepted: list[tuple[str, EvidenceEdge, float]] = []
            for origin, origin_rows in by_origin.items():
                strongest = max(origin_rows, key=lambda e: e.confidence)
                if strongest.confidence < min_confidence:
                    continue
                reliability = self.origin_reliability(origin, metric=reliability_metric)
                if min_origin_reliability is not None and reliability < min_origin_reliability:
                    continue
                accepted.append((origin, strongest, reliability))
            if len(accepted) < min_independent_origins:
                continue
            accepted.sort(key=lambda item: item[0])
            representative = max(rows, key=lambda e: (e.epoch, e.evidence_id))
            origins = tuple(item[0] for item in accepted)
            best_conf = max(item[1].confidence for item in accepted)
            reliability_floor = min(item[2] for item in accepted)
            adjacency[s].append((representative, origins, best_conf, reliability_floor))
            canonical.setdefault(s, representative.subject)
            canonical.setdefault(o, representative.object)

        source_key, target_key = self._key(source), self._key(target)
        queue = [(source_key, (source,), (), (), (), (), (), ())]
        paths: list[EvidencePath] = []
        while queue and len(paths) < max_paths:
            node, nodes, predicates, evidence_ids, texts, origins_by_edge, confs, rels = queue.pop(0)
            if len(predicates) >= max_hops:
                continue
            for edge, origins, conf, rel in sorted(
                adjacency.get(node, ()), key=lambda x: (self._key(x[0].object), x[0].predicate, x[0].evidence_id)
            ):
                nxt = self._key(edge.object)
                if nxt in {self._key(n) for n in nodes}:
                    continue
                nn = (*nodes, canonical.get(nxt, edge.object))
                np = (*predicates, edge.predicate)
                ne = (*evidence_ids, edge.evidence_id)
                nt = (*texts, edge.source_text)
                no = (*origins_by_edge, origins)
                nc = (*confs, conf)
                nr = (*rels, rel)
                if nxt == target_key:
                    paths.append(EvidencePath(
                        nn, np, ne, nt, no, nc, nr, len(np), min(nc),
                        min(len(x) for x in no), min(nr)
                    ))
                else:
                    queue.append((nxt, nn, np, ne, nt, no, nc, nr))
        paths.sort(key=lambda p: (-p.independent_origin_floor, -p.reliability_floor, -p.confidence, p.hops, p.nodes))
        return EvidenceInferenceResult(source, target, tuple(paths[:max_paths]), bool(paths), 0)
