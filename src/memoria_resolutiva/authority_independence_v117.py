from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .adjudication_cycle_guard_v116 import AdjudicationCycleGuardMemoryV116
from .source_reliability_v115 import ReliableCorroboratedEdgeV115
from .structural_inference_v111 import StructuralPathV111


@dataclass(frozen=True, slots=True)
class AuthorityQualifiedEdgeV117:
    edge: ReliableCorroboratedEdgeV115
    independent_authorities: tuple[str, ...]
    origins_by_authority: tuple[tuple[str, tuple[str, ...]], ...]
    authority_confidences: tuple[tuple[str, float], ...]
    authority_reliabilities: tuple[tuple[str, float], ...]
    confidence: float
    reliability_floor: float


@dataclass(frozen=True, slots=True)
class AuthorityQualifiedPathV117:
    path: StructuralPathV111
    confidence: float
    independent_origin_floor: int
    independent_authority_floor: int
    reliability_floor: float
    authorities_by_edge: tuple[tuple[str, ...], ...]
    origins_by_edge: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class AuthorityInferenceResultV117:
    source: str
    target: str
    paths: tuple[AuthorityQualifiedPathV117, ...]
    inferred: bool
    unsupported_claims: int = 0


class AuthorityIndependenceMemoryV117(AdjudicationCycleGuardMemoryV116):
    """v1.16 plus authority-level independence to reduce Sybil inflation.

    An ``origin`` is still the concrete evidence family used by v1.14-v1.16.
    ``authority_id`` identifies the controlling or trust-root authority behind one
    or more origins. Several origins mapped to the same authority count as one
    independent authority, so aliases cannot satisfy an authority gate merely by
    multiplying identities.

    Authority membership is explicit and auditable. When no mapping is supplied,
    an origin defaults to its own authority id, preserving previous semantics.
    Confidence and reliability are not fused across authorities: each authority
    contributes the strongest accepted origin confidence while its reliability is
    conservatively represented by the weakest accepted origin from that authority.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._authority_by_origin: dict[str, str] = {}

    def register_origin_authority(self, origin: str, authority_id: str) -> None:
        origin = self._clean_identity(origin, field="origin")
        authority_id = self._clean_identity(authority_id, field="authority_id")
        existing = self._authority_by_origin.get(origin)
        if existing is not None and existing != authority_id:
            raise ValueError("origin authority is immutable once registered")
        self._authority_by_origin[origin] = authority_id

    def authority_for_origin(self, origin: str) -> str:
        origin = self._clean_identity(origin, field="origin")
        return self._authority_by_origin.get(origin, origin)

    def authority_snapshot(self) -> dict[str, str]:
        return dict(sorted(self._authority_by_origin.items()))

    def authority_edges(
        self,
        *,
        namespace: str | None = None,
        epoch: int | None = None,
        min_confidence: float = 0.0,
        min_independent_origins: int = 1,
        min_origin_reliability: float | None = None,
        reliability_metric: str = "posterior",
        min_independent_authorities: int = 1,
    ) -> tuple[AuthorityQualifiedEdgeV117, ...]:
        if min_independent_authorities < 1:
            raise ValueError("min_independent_authorities must be >= 1")

        baseline = super().reliable_edges(
            namespace=namespace,
            epoch=epoch,
            min_confidence=min_confidence,
            min_independent_origins=min_independent_origins,
            min_origin_reliability=min_origin_reliability,
            reliability_metric=reliability_metric,
        )
        out: list[AuthorityQualifiedEdgeV117] = []
        for wrapped in baseline:
            accepted_conf = dict(wrapped.edge.origin_confidences)
            accepted_rel = dict(wrapped.origin_reliabilities)
            grouped: dict[str, list[str]] = defaultdict(list)
            for origin in wrapped.accepted_origins:
                grouped[self.authority_for_origin(origin)].append(origin)

            if len(grouped) < min_independent_authorities:
                continue

            authority_confidences: list[tuple[str, float]] = []
            authority_reliabilities: list[tuple[str, float]] = []
            origins_by_authority: list[tuple[str, tuple[str, ...]]] = []
            for authority, origins in sorted(grouped.items()):
                origins = sorted(origins)
                origins_by_authority.append((authority, tuple(origins)))
                authority_confidences.append(
                    (authority, max(accepted_conf[origin] for origin in origins))
                )
                authority_reliabilities.append(
                    (authority, min(accepted_rel[origin] for origin in origins))
                )

            out.append(
                AuthorityQualifiedEdgeV117(
                    edge=wrapped,
                    independent_authorities=tuple(sorted(grouped)),
                    origins_by_authority=tuple(origins_by_authority),
                    authority_confidences=tuple(authority_confidences),
                    authority_reliabilities=tuple(authority_reliabilities),
                    confidence=max(score for _, score in authority_confidences),
                    reliability_floor=min(score for _, score in authority_reliabilities),
                )
            )
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
        min_confidence: float = 0.0,
        min_independent_origins: int = 1,
        min_origin_reliability: float | None = None,
        reliability_metric: str = "posterior",
        min_independent_authorities: int = 1,
    ) -> AuthorityInferenceResultV117:
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        if max_paths < 1:
            raise ValueError("max_paths must be >= 1")

        adjacency: dict[str, list[AuthorityQualifiedEdgeV117]] = defaultdict(list)
        canonical: dict[str, str] = {}
        for wrapped in self.authority_edges(
            namespace=namespace,
            epoch=epoch,
            min_confidence=min_confidence,
            min_independent_origins=min_independent_origins,
            min_origin_reliability=min_origin_reliability,
            reliability_metric=reliability_metric,
            min_independent_authorities=min_independent_authorities,
        ):
            edge = wrapped.edge.edge.edge
            s, o = self._key(edge.subject), self._key(edge.object)
            adjacency[s].append(wrapped)
            canonical.setdefault(s, edge.subject)
            canonical.setdefault(o, edge.object)

        source_key = self._key(source)
        target_key = self._key(target)
        queue = [(source_key, (source,), (), (), (), ())]
        paths: list[AuthorityQualifiedPathV117] = []
        while queue and len(paths) < max_paths:
            node, nodes, predicates, memory_ids, source_texts, wrappers = queue.pop(0)
            if len(predicates) >= max_hops:
                continue
            for wrapped in sorted(
                adjacency.get(node, ()),
                key=lambda item: (
                    -len(item.independent_authorities),
                    -item.reliability_floor,
                    -item.confidence,
                    self._key(item.edge.edge.edge.object),
                ),
            ):
                edge = wrapped.edge.edge.edge
                nxt = self._key(edge.object)
                if nxt in {self._key(item) for item in nodes}:
                    continue
                new_nodes = (*nodes, canonical.get(nxt, edge.object))
                new_predicates = (*predicates, edge.predicate)
                new_memory_ids = (*memory_ids, edge.memory_id)
                new_source_texts = (*source_texts, edge.source_text)
                new_wrappers = (*wrappers, wrapped)
                if nxt == target_key:
                    path = StructuralPathV111(
                        nodes=new_nodes,
                        predicates=new_predicates,
                        memory_ids=new_memory_ids,
                        source_texts=new_source_texts,
                        hops=len(new_predicates),
                    )
                    paths.append(
                        AuthorityQualifiedPathV117(
                            path=path,
                            confidence=min(item.confidence for item in new_wrappers),
                            independent_origin_floor=min(
                                len(item.edge.accepted_origins) for item in new_wrappers
                            ),
                            independent_authority_floor=min(
                                len(item.independent_authorities) for item in new_wrappers
                            ),
                            reliability_floor=min(
                                item.reliability_floor for item in new_wrappers
                            ),
                            authorities_by_edge=tuple(
                                item.independent_authorities for item in new_wrappers
                            ),
                            origins_by_edge=tuple(
                                item.edge.accepted_origins for item in new_wrappers
                            ),
                        )
                    )
                else:
                    queue.append((
                        nxt,
                        new_nodes,
                        new_predicates,
                        new_memory_ids,
                        new_source_texts,
                        new_wrappers,
                    ))

        paths.sort(key=lambda item: (
            -item.independent_authority_floor,
            -item.independent_origin_floor,
            -item.reliability_floor,
            -item.confidence,
            item.path.hops,
            item.path.nodes,
        ))
        return AuthorityInferenceResultV117(
            source=source,
            target=target,
            paths=tuple(paths[:max_paths]),
            inferred=bool(paths),
            unsupported_claims=0,
        )
