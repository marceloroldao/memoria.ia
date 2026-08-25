from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .authority_attestation_v118 import AuthorityAttestationMemoryV118
from .authority_independence_v117 import (
    AuthorityIndependenceMemoryV117,
    AuthorityInferenceResultV117,
    AuthorityQualifiedEdgeV117,
    AuthorityQualifiedPathV117,
)
from .structural_inference_v111 import StructuralPathV111


@dataclass(frozen=True, slots=True)
class AuthorityLifecycleV119:
    authority_id: str
    issuer_id: str
    attestation_id: str
    valid_from_epoch: int
    expires_at_epoch: int | None


@dataclass(frozen=True, slots=True)
class AuthorityRevocationV119:
    revocation_id: str
    authority_id: str
    issuer_id: str
    revoked_at_epoch: int


class AttestationLifecycleMemoryV119(AuthorityAttestationMemoryV118):
    """v1.18 plus deterministic attestation validity, expiry and revocation.

    The core intentionally does not read wall-clock time. A monotonic policy epoch
    is supplied by the embedding application. Attestations can become valid at a
    chosen epoch, can expire at an exclusive epoch, and can be revoked only by the
    issuer that created the original attestation. History remains append-only.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._policy_epoch = 0
        self._lifecycles: dict[str, AuthorityLifecycleV119] = {}
        self._revocations: dict[str, AuthorityRevocationV119] = {}
        self._revocation_by_authority: dict[str, AuthorityRevocationV119] = {}

    @property
    def policy_epoch(self) -> int:
        return self._policy_epoch

    def set_policy_epoch(self, epoch: int) -> None:
        if epoch < 0:
            raise ValueError("policy epoch must be >= 0")
        if epoch < self._policy_epoch:
            raise ValueError("policy epoch cannot move backwards")
        self._policy_epoch = epoch

    def attest_authority(
        self,
        authority_id: str,
        *,
        issuer_id: str,
        attestation_id: str,
        valid_from_epoch: int | None = None,
        expires_at_epoch: int | None = None,
    ):
        start = self._policy_epoch if valid_from_epoch is None else valid_from_epoch
        if start < 0:
            raise ValueError("valid_from_epoch must be >= 0")
        if expires_at_epoch is not None and expires_at_epoch <= start:
            raise ValueError("expires_at_epoch must be greater than valid_from_epoch")

        record = super().attest_authority(
            authority_id,
            issuer_id=issuer_id,
            attestation_id=attestation_id,
        )
        self._lifecycles[record.authority_id] = AuthorityLifecycleV119(
            authority_id=record.authority_id,
            issuer_id=record.issuer_id,
            attestation_id=record.attestation_id,
            valid_from_epoch=start,
            expires_at_epoch=expires_at_epoch,
        )
        return record

    def revoke_authority(
        self,
        authority_id: str,
        *,
        issuer_id: str,
        revocation_id: str,
        revoked_at_epoch: int | None = None,
    ) -> AuthorityRevocationV119:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        issuer_id = self._clean_identity(issuer_id, field="issuer_id")
        revocation_id = self._clean_identity(revocation_id, field="revocation_id")
        if revocation_id in self._revocations:
            raise ValueError("revocation_id has already been applied")
        lifecycle = self._lifecycles.get(authority_id)
        if lifecycle is None:
            raise ValueError("authority has no attestation to revoke")
        if lifecycle.issuer_id != issuer_id:
            raise ValueError("only the original attestation issuer may revoke authority")
        if authority_id in self._revocation_by_authority:
            raise ValueError("authority attestation is already revoked")
        when = self._policy_epoch if revoked_at_epoch is None else revoked_at_epoch
        if when < lifecycle.valid_from_epoch:
            raise ValueError("revoked_at_epoch cannot precede attestation validity")
        record = AuthorityRevocationV119(
            revocation_id=revocation_id,
            authority_id=authority_id,
            issuer_id=issuer_id,
            revoked_at_epoch=when,
        )
        self._revocations[revocation_id] = record
        self._revocation_by_authority[authority_id] = record
        return record

    def is_authority_verified(self, authority_id: str, *, epoch: int | None = None) -> bool:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        lifecycle = self._lifecycles.get(authority_id)
        if lifecycle is None:
            return False
        at = self._policy_epoch if epoch is None else epoch
        if at < 0:
            raise ValueError("epoch must be >= 0")
        if at < lifecycle.valid_from_epoch:
            return False
        if lifecycle.expires_at_epoch is not None and at >= lifecycle.expires_at_epoch:
            return False
        revoked = self._revocation_by_authority.get(authority_id)
        if revoked is not None and at >= revoked.revoked_at_epoch:
            return False
        return True

    def authority_lifecycles(self) -> tuple[AuthorityLifecycleV119, ...]:
        return tuple(sorted(self._lifecycles.values(), key=lambda item: item.authority_id))

    def authority_revocations(self) -> tuple[AuthorityRevocationV119, ...]:
        return tuple(sorted(self._revocations.values(), key=lambda item: item.revocation_id))

    def authority_edges(
        self,
        *,
        require_verified_authorities: bool = False,
        min_verified_authorities: int = 1,
        authority_epoch: int | None = None,
        **kwargs,
    ) -> tuple[AuthorityQualifiedEdgeV117, ...]:
        if min_verified_authorities < 1:
            raise ValueError("min_verified_authorities must be >= 1")
        baseline = AuthorityIndependenceMemoryV117.authority_edges(self, **kwargs)
        if not require_verified_authorities:
            return baseline
        out = []
        for wrapped in baseline:
            verified = tuple(
                authority
                for authority in wrapped.independent_authorities
                if self.is_authority_verified(authority, epoch=authority_epoch)
            )
            if len(verified) >= min_verified_authorities:
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
        authority_epoch: int | None = None,
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
            require_verified_authorities=require_verified_authorities,
            min_verified_authorities=min_verified_authorities,
            authority_epoch=authority_epoch,
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
