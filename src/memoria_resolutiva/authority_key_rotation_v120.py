from __future__ import annotations

from dataclasses import dataclass

from .attestation_lifecycle_v119 import AttestationLifecycleMemoryV119


@dataclass(frozen=True, slots=True)
class AuthorityKeyBindingV120:
    binding_id: str
    authority_id: str
    key_id: str
    bound_by_issuer: str
    valid_from_epoch: int


@dataclass(frozen=True, slots=True)
class AuthorityKeyRotationV120:
    rotation_id: str
    authority_id: str
    previous_key_id: str
    new_key_id: str
    continuity_evidence_id: str
    effective_epoch: int


class AuthorityKeyRotationMemoryV120(AttestationLifecycleMemoryV119):
    """v1.19 plus deterministic authority-key continuity.

    The memory core does not verify cryptographic signatures. The embedding
    identity layer must validate the continuity proof before calling
    ``rotate_authority_key`` and pass an auditable ``continuity_evidence_id``.

    An authority is a stable logical identity; keys are replaceable credentials.
    A new key never inherits authority identity merely by being observed. It must
    be introduced through an append-only rotation from the key that was active at
    the effective policy epoch. Historical key queries remain deterministic.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._key_bindings: dict[str, AuthorityKeyBindingV120] = {}
        self._initial_binding_by_authority: dict[str, AuthorityKeyBindingV120] = {}
        self._authority_by_key: dict[str, str] = {}
        self._rotations: dict[str, AuthorityKeyRotationV120] = {}
        self._continuity_evidence_ids: set[str] = set()

    def bind_initial_authority_key(
        self,
        authority_id: str,
        *,
        key_id: str,
        issuer_id: str,
        binding_id: str,
        valid_from_epoch: int | None = None,
    ) -> AuthorityKeyBindingV120:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        key_id = self._clean_identity(key_id, field="key_id")
        issuer_id = self._clean_identity(issuer_id, field="issuer_id")
        binding_id = self._clean_identity(binding_id, field="binding_id")
        lifecycle = self._lifecycles.get(authority_id)
        if lifecycle is None:
            raise ValueError("authority must be attested before binding a key")
        if lifecycle.issuer_id != issuer_id:
            raise ValueError("initial key binding must be authorized by attestation issuer")
        if authority_id in self._initial_binding_by_authority:
            raise ValueError("authority already has an initial key binding")
        if binding_id in self._key_bindings:
            raise ValueError("binding_id has already been applied")
        if key_id in self._authority_by_key:
            raise ValueError("key_id is already bound to an authority")
        start = lifecycle.valid_from_epoch if valid_from_epoch is None else valid_from_epoch
        if start < lifecycle.valid_from_epoch:
            raise ValueError("key cannot become valid before authority attestation")
        record = AuthorityKeyBindingV120(
            binding_id=binding_id,
            authority_id=authority_id,
            key_id=key_id,
            bound_by_issuer=issuer_id,
            valid_from_epoch=start,
        )
        self._key_bindings[binding_id] = record
        self._initial_binding_by_authority[authority_id] = record
        self._authority_by_key[key_id] = authority_id
        return record

    def rotate_authority_key(
        self,
        authority_id: str,
        *,
        previous_key_id: str,
        new_key_id: str,
        rotation_id: str,
        continuity_evidence_id: str,
        effective_epoch: int | None = None,
    ) -> AuthorityKeyRotationV120:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        previous_key_id = self._clean_identity(previous_key_id, field="previous_key_id")
        new_key_id = self._clean_identity(new_key_id, field="new_key_id")
        rotation_id = self._clean_identity(rotation_id, field="rotation_id")
        continuity_evidence_id = self._clean_identity(
            continuity_evidence_id, field="continuity_evidence_id"
        )
        if rotation_id in self._rotations:
            raise ValueError("rotation_id has already been applied")
        if continuity_evidence_id in self._continuity_evidence_ids:
            raise ValueError("continuity_evidence_id has already been applied")
        if new_key_id in self._authority_by_key:
            raise ValueError("new_key_id is already bound to an authority")
        when = self.policy_epoch if effective_epoch is None else effective_epoch
        if when < 0:
            raise ValueError("effective_epoch must be >= 0")
        active = self.active_authority_key(authority_id, epoch=when)
        if active is None:
            raise ValueError("authority has no active key at effective_epoch")
        if active != previous_key_id:
            raise ValueError("previous_key_id is not the active authority key")
        record = AuthorityKeyRotationV120(
            rotation_id=rotation_id,
            authority_id=authority_id,
            previous_key_id=previous_key_id,
            new_key_id=new_key_id,
            continuity_evidence_id=continuity_evidence_id,
            effective_epoch=when,
        )
        self._rotations[rotation_id] = record
        self._continuity_evidence_ids.add(continuity_evidence_id)
        self._authority_by_key[new_key_id] = authority_id
        return record

    def active_authority_key(self, authority_id: str, *, epoch: int | None = None) -> str | None:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        binding = self._initial_binding_by_authority.get(authority_id)
        if binding is None:
            return None
        at = self.policy_epoch if epoch is None else epoch
        if at < 0:
            raise ValueError("epoch must be >= 0")
        if at < binding.valid_from_epoch:
            return None
        key_id = binding.key_id
        rotations = sorted(
            (
                item
                for item in self._rotations.values()
                if item.authority_id == authority_id and item.effective_epoch <= at
            ),
            key=lambda item: (item.effective_epoch, item.rotation_id),
        )
        for item in rotations:
            if item.previous_key_id != key_id:
                # Append-only history may contain no fork because rotate_authority_key
                # validates the active predecessor. Keep this guard for audit safety.
                continue
            key_id = item.new_key_id
        return key_id

    def authority_for_key(self, key_id: str) -> str | None:
        key_id = self._clean_identity(key_id, field="key_id")
        return self._authority_by_key.get(key_id)

    def is_authority_key_active(
        self,
        authority_id: str,
        key_id: str,
        *,
        epoch: int | None = None,
        require_verified_authority: bool = True,
    ) -> bool:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        key_id = self._clean_identity(key_id, field="key_id")
        at = self.policy_epoch if epoch is None else epoch
        if require_verified_authority and not self.is_authority_verified(authority_id, epoch=at):
            return False
        return self.active_authority_key(authority_id, epoch=at) == key_id

    def authority_key_bindings(self) -> tuple[AuthorityKeyBindingV120, ...]:
        return tuple(sorted(self._key_bindings.values(), key=lambda item: item.binding_id))

    def authority_key_rotations(self) -> tuple[AuthorityKeyRotationV120, ...]:
        return tuple(sorted(self._rotations.values(), key=lambda item: item.rotation_id))
