from __future__ import annotations

from dataclasses import dataclass

from .authority_independence_v117 import (
    AuthorityIndependenceMemoryV117,
    AuthorityQualifiedEdgeV117,
    AuthorityQualifiedPathV117,
    AuthorityInferenceResultV117,
)


@dataclass(frozen=True, slots=True)
class AuthorityAttestationV118:
    attestation_id: str
    authority_id: str
    issuer_id: str


class AuthorityAttestationMemoryV118(AuthorityIndependenceMemoryV117):
    """v1.17 plus trusted-root attestations for authority identities.

    Authority diversity only has Sybil-resistance value when authority identities
    themselves are anchored. This layer therefore distinguishes configured trust
    roots from ordinary authorities. An authority is considered verified only
    after a unique attestation issued by a configured trusted issuer.

    The registry is intentionally explicit: no authority is auto-verified merely
    because it exists, owns an origin, or adjudicates another source. Trust-root
    configuration is an external policy decision and is never inferred from the
    memory graph.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._trusted_issuers: set[str] = set()
        self._attestations: dict[str, AuthorityAttestationV118] = {}
        self._attestation_by_authority: dict[str, AuthorityAttestationV118] = {}

    def add_trusted_issuer(self, issuer_id: str) -> None:
        issuer_id = self._clean_identity(issuer_id, field="issuer_id")
        self._trusted_issuers.add(issuer_id)

    def trusted_issuers(self) -> tuple[str, ...]:
        return tuple(sorted(self._trusted_issuers))

    def attest_authority(
        self,
        authority_id: str,
        *,
        issuer_id: str,
        attestation_id: str,
    ) -> AuthorityAttestationV118:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        issuer_id = self._clean_identity(issuer_id, field="issuer_id")
        attestation_id = self._clean_identity(attestation_id, field="attestation_id")
        if issuer_id not in self._trusted_issuers:
            raise ValueError("issuer_id is not configured as a trusted issuer")
        if attestation_id in self._attestations:
            raise ValueError("attestation_id has already been applied")
        existing = self._attestation_by_authority.get(authority_id)
        if existing is not None:
            if existing.issuer_id == issuer_id:
                raise ValueError("authority is already attested")
            raise ValueError("authority attestation is immutable once established")
        record = AuthorityAttestationV118(
            attestation_id=attestation_id,
            authority_id=authority_id,
            issuer_id=issuer_id,
        )
        self._attestations[attestation_id] = record
        self._attestation_by_authority[authority_id] = record
        return record

    def is_authority_verified(self, authority_id: str) -> bool:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        return authority_id in self._attestation_by_authority

    def authority_attestations(self) -> tuple[AuthorityAttestationV118, ...]:
        return tuple(sorted(self._attestations.values(), key=lambda item: item.attestation_id))

    def authority_edges(
        self,
        *,
        require_verified_authorities: bool = False,
        min_verified_authorities: int = 1,
        **kwargs,
    ) -> tuple[AuthorityQualifiedEdgeV117, ...]:
        if min_verified_authorities < 1:
            raise ValueError("min_verified_authorities must be >= 1")
        baseline = super().authority_edges(**kwargs)
        if not require_verified_authorities:
            return baseline

        out = []
        for wrapped in baseline:
            verified = tuple(
                authority
                for authority in wrapped.independent_authorities
                if self.is_authority_verified(authority)
            )
            if len(verified) < min_verified_authorities:
                continue
            # Reuse the v1.17 edge because verification is a gate, not a fused score.
            out.append(wrapped)
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
        require_verified_authorities: bool = False,
        min_verified_authorities: int = 1,
    ) -> AuthorityInferenceResultV117:
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        if max_paths < 1:
            raise ValueError("max_paths must be >= 1")

        # Filter at edge level, then run the same BFS semantics as v1.17.
        from collections import defaultdict
        from .structural_inference_v111 import StructuralPathV111

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
            require_verified_authorities=require_verified_authorities,
            min_verified_authorities=min_verified_authorities,
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
                            reliability_floor=min(item.reliability_floor for item in new_wrappers),
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
