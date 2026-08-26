from __future__ import annotations

from dataclasses import dataclass

from .authority_key_rotation_v120 import AuthorityKeyRotationMemoryV120


@dataclass(frozen=True, slots=True)
class AuthorityKeyCompromiseV121:
    compromise_id: str
    authority_id: str
    key_id: str
    reported_by_issuer: str
    compromised_at_epoch: int


@dataclass(frozen=True, slots=True)
class AuthorityKeyRecoveryV121:
    recovery_id: str
    authority_id: str
    compromised_key_id: str
    replacement_key_id: str
    recovery_evidence_id: str
    authorized_by_issuer: str
    effective_epoch: int


class KeyCompromiseRecoveryMemoryV121(AuthorityKeyRotationMemoryV120):
    """v1.20 plus deterministic emergency recovery from compromised keys.

    Normal rotation still requires continuity from the active predecessor. Emergency
    recovery is a separate path for cases where that predecessor must no longer be
    trusted. The memory core does not validate cryptographic recovery proofs; the
    embedding identity layer validates them externally and passes an auditable
    ``recovery_evidence_id``.

    A compromise quarantines the affected key from the incident epoch onward while
    preserving historical validity before that epoch. Recovery requires the original
    authority attestation issuer, a fresh replacement key, and replay-protected
    recovery identifiers.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._compromises: dict[str, AuthorityKeyCompromiseV121] = {}
        self._compromise_by_key: dict[str, AuthorityKeyCompromiseV121] = {}
        self._recoveries: dict[str, AuthorityKeyRecoveryV121] = {}
        self._recovery_evidence_ids: set[str] = set()

    def report_key_compromise(
        self,
        authority_id: str,
        *,
        key_id: str,
        issuer_id: str,
        compromise_id: str,
        compromised_at_epoch: int | None = None,
    ) -> AuthorityKeyCompromiseV121:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        key_id = self._clean_identity(key_id, field="key_id")
        issuer_id = self._clean_identity(issuer_id, field="issuer_id")
        compromise_id = self._clean_identity(compromise_id, field="compromise_id")
        if compromise_id in self._compromises:
            raise ValueError("compromise_id has already been applied")
        lifecycle = self._lifecycles.get(authority_id)
        if lifecycle is None:
            raise ValueError("authority must be attested before reporting compromise")
        if lifecycle.issuer_id != issuer_id:
            raise ValueError("key compromise must be authorized by attestation issuer")
        if self.authority_for_key(key_id) != authority_id:
            raise ValueError("key_id is not bound to authority")
        if key_id in self._compromise_by_key:
            raise ValueError("key_id is already marked compromised")
        when = self.policy_epoch if compromised_at_epoch is None else compromised_at_epoch
        if when < 0:
            raise ValueError("compromised_at_epoch must be >= 0")
        if self.active_authority_key(authority_id, epoch=when) != key_id:
            raise ValueError("only the key active at compromised_at_epoch can be compromised")
        record = AuthorityKeyCompromiseV121(
            compromise_id=compromise_id,
            authority_id=authority_id,
            key_id=key_id,
            reported_by_issuer=issuer_id,
            compromised_at_epoch=when,
        )
        self._compromises[compromise_id] = record
        self._compromise_by_key[key_id] = record
        return record

    def recover_authority_key(
        self,
        authority_id: str,
        *,
        compromised_key_id: str,
        replacement_key_id: str,
        issuer_id: str,
        recovery_id: str,
        recovery_evidence_id: str,
        effective_epoch: int | None = None,
    ) -> AuthorityKeyRecoveryV121:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        compromised_key_id = self._clean_identity(
            compromised_key_id, field="compromised_key_id"
        )
        replacement_key_id = self._clean_identity(
            replacement_key_id, field="replacement_key_id"
        )
        issuer_id = self._clean_identity(issuer_id, field="issuer_id")
        recovery_id = self._clean_identity(recovery_id, field="recovery_id")
        recovery_evidence_id = self._clean_identity(
            recovery_evidence_id, field="recovery_evidence_id"
        )
        if recovery_id in self._recoveries:
            raise ValueError("recovery_id has already been applied")
        if recovery_evidence_id in self._recovery_evidence_ids:
            raise ValueError("recovery_evidence_id has already been applied")
        lifecycle = self._lifecycles.get(authority_id)
        if lifecycle is None:
            raise ValueError("authority must be attested before recovery")
        if lifecycle.issuer_id != issuer_id:
            raise ValueError("recovery must be authorized by attestation issuer")
        compromise = self._compromise_by_key.get(compromised_key_id)
        if compromise is None or compromise.authority_id != authority_id:
            raise ValueError("compromised_key_id has no matching compromise record")
        if replacement_key_id in self._authority_by_key:
            raise ValueError("replacement_key_id is already bound to an authority")
        when = self.policy_epoch if effective_epoch is None else effective_epoch
        if when < compromise.compromised_at_epoch:
            raise ValueError("recovery cannot precede key compromise")
        if any(item.authority_id == authority_id and item.effective_epoch >= compromise.compromised_at_epoch for item in self._recoveries.values()):
            raise ValueError("authority already has a recovery for this compromise interval")
        record = AuthorityKeyRecoveryV121(
            recovery_id=recovery_id,
            authority_id=authority_id,
            compromised_key_id=compromised_key_id,
            replacement_key_id=replacement_key_id,
            recovery_evidence_id=recovery_evidence_id,
            authorized_by_issuer=issuer_id,
            effective_epoch=when,
        )
        self._recoveries[recovery_id] = record
        self._recovery_evidence_ids.add(recovery_evidence_id)
        self._authority_by_key[replacement_key_id] = authority_id
        return record

    def active_authority_key(self, authority_id: str, *, epoch: int | None = None) -> str | None:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        at = self.policy_epoch if epoch is None else epoch
        if at < 0:
            raise ValueError("epoch must be >= 0")

        key_id = super().active_authority_key(authority_id, epoch=at)
        if key_id is None:
            return None

        compromise = self._compromise_by_key.get(key_id)
        if compromise is None or at < compromise.compromised_at_epoch:
            return key_id

        recoveries = sorted(
            (
                item
                for item in self._recoveries.values()
                if item.authority_id == authority_id
                and item.compromised_key_id == key_id
                and item.effective_epoch <= at
            ),
            key=lambda item: (item.effective_epoch, item.recovery_id),
        )
        if not recoveries:
            return None
        return recoveries[-1].replacement_key_id

    def rotate_authority_key(self, authority_id: str, **kwargs):
        previous_key_id = self._clean_identity(
            kwargs.get("previous_key_id", ""), field="previous_key_id"
        )
        effective_epoch = kwargs.get("effective_epoch")
        at = self.policy_epoch if effective_epoch is None else effective_epoch
        compromise = self._compromise_by_key.get(previous_key_id)
        if compromise is not None and at >= compromise.compromised_at_epoch:
            raise ValueError("compromised key cannot authorize normal rotation")
        return super().rotate_authority_key(authority_id, **kwargs)

    def authority_key_compromises(self) -> tuple[AuthorityKeyCompromiseV121, ...]:
        return tuple(sorted(self._compromises.values(), key=lambda item: item.compromise_id))

    def authority_key_recoveries(self) -> tuple[AuthorityKeyRecoveryV121, ...]:
        return tuple(sorted(self._recoveries.values(), key=lambda item: item.recovery_id))
