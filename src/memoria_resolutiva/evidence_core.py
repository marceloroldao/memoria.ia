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

    def iter_evidence(self) -> tuple[EvidenceEdge, ...]:
        """Return the complete evidence catalog across namespaces in insertion order.

        This does not project current state and does not change namespace-scoped
        `evidence_history` semantics. It exists for cross-namespace audit/restart
        validation where evidence ids must be resolved independently of namespace.
        """
        return tuple(self._edges)

    def evidence_history(self, *, namespace: str | None = None, epoch: int | None = None) -> tuple[EvidenceEdge, ...]:
        """Return preserved evidence rows without collapsing them to current state.

        ``active_edges`` intentionally projects the latest state for each
        subject/predicate slot. Consolidation and audit need the complementary
        view: every persisted observation, while provenance decides whether a
        historical support still has active factual lineage.
        """
        return self._visible(namespace, epoch)

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
        if reliability_metric not in {"posterior", "wilson"}:
            raise ValueError("reliability_metric must be 'posterior' or 'wilson'")
        source_key = self._key(source)
        target_key = self._key(target)
        adjacency: dict[str, list[EvidenceEdge]] = defaultdict(list)
        for edge in self.active_edges(namespace=namespace, epoch=epoch):
            adjacency[self._key(edge.subject)].append(edge)

        queue = deque([(source_key, (source,), (), (), (), (), (), 1.0, frozenset({source_key}))])
        found: list[EvidencePath] = []
        unsupported_claims = 0
        while queue and len(found) < max_paths:
            node, nodes, predicates, evidence_ids, texts, origins_by_edge, confidences, confidence, seen = queue.popleft()
            if len(predicates) >= max_hops:
                continue
            for edge in adjacency.get(node, ()):
                edge_origins = tuple(sorted({part.strip() for part in edge.origin.split("+") if part.strip()})) or (edge.origin,)
                independent = len(edge_origins)
                reliability_values = tuple(self.origin_reliability(origin, metric=reliability_metric) for origin in edge_origins)
                reliability_floor = min(reliability_values) if reliability_values else 1.0
                next_confidence = confidence * edge.confidence * reliability_floor
                if edge.confidence < min_confidence or independent < min_independent_origins:
                    unsupported_claims += 1
                    continue
                if min_origin_reliability is not None and reliability_floor < min_origin_reliability:
                    unsupported_claims += 1
                    continue
                next_node = self._key(edge.object)
                if next_node in seen:
                    continue
                next_nodes = nodes + (edge.object,)
                next_predicates = predicates + (edge.predicate,)
                next_ids = evidence_ids + (edge.evidence_id,)
                next_texts = texts + (edge.source_text,)
                next_origins = origins_by_edge + (edge_origins,)
                next_confidences = confidences + (edge.confidence,)
                next_seen = seen | {next_node}
                if next_node == target_key:
                    all_reliabilities = tuple(
                        self.origin_reliability(origin, metric=reliability_metric)
                        for origins in next_origins for origin in origins
                    )
                    found.append(EvidencePath(
                        next_nodes,
                        next_predicates,
                        next_ids,
                        next_texts,
                        next_origins,
                        next_confidences,
                        all_reliabilities,
                        len(next_predicates),
                        next_confidence,
                        min((len(origins) for origins in next_origins), default=0),
                        min(all_reliabilities, default=1.0),
                    ))
                    if len(found) >= max_paths:
                        break
                else:
                    queue.append((
                        next_node,
                        next_nodes,
                        next_predicates,
                        next_ids,
                        next_texts,
                        next_origins,
                        next_confidences,
                        next_confidence,
                        next_seen,
                    ))
        found.sort(key=lambda p: (-p.confidence, p.hops, p.evidence_ids))
        return EvidenceInferenceResult(source, target, tuple(found[:max_paths]), bool(found), unsupported_claims)
