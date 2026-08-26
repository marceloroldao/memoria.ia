from __future__ import annotations

from dataclasses import dataclass

from .key_compromise_recovery_v121 import KeyCompromiseRecoveryMemoryV121


@dataclass(frozen=True, slots=True)
class RecoveryApprovalV122:
    approval_id: str
    authority_id: str
    compromised_key_id: str
    replacement_key_id: str
    approver_id: str
    recovery_evidence_id: str
    effective_epoch: int


class RecoveryQuorumMemoryV122(KeyCompromiseRecoveryMemoryV121):
    """v1.21 plus independent multi-approver recovery quorum.

    Approvers are configured explicitly per logical authority. A recovery may only
    be committed after the configured threshold of distinct approvers has approved
    the same compromised key, replacement key and recovery evidence tuple.
    The core does not verify cryptographic signatures; the embedding identity layer
    validates each approval externally before recording it here.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._recovery_policy: dict[str, tuple[frozenset[str], int]] = {}
        self._recovery_approvals: dict[str, RecoveryApprovalV122] = {}
        self._approval_ids: set[str] = set()

    def configure_recovery_quorum(
        self,
        authority_id: str,
        *,
        approver_ids,
        threshold: int,
    ) -> None:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        cleaned = frozenset(
            self._clean_identity(item, field="approver_id") for item in approver_ids
        )
        if not cleaned:
            raise ValueError("at least one recovery approver is required")
        if threshold < 1 or threshold > len(cleaned):
            raise ValueError("threshold must be between 1 and number of approvers")
        existing = self._recovery_policy.get(authority_id)
        policy = (cleaned, threshold)
        if existing is not None and existing != policy:
            raise ValueError("recovery quorum policy is immutable once configured")
        self._recovery_policy[authority_id] = policy

    def approve_recovery(
        self,
        authority_id: str,
        *,
        compromised_key_id: str,
        replacement_key_id: str,
        approver_id: str,
        approval_id: str,
        recovery_evidence_id: str,
        effective_epoch: int | None = None,
    ) -> RecoveryApprovalV122:
        authority_id = self._clean_identity(authority_id, field="authority_id")
        compromised_key_id = self._clean_identity(compromised_key_id, field="compromised_key_id")
        replacement_key_id = self._clean_identity(replacement_key_id, field="replacement_key_id")
        approver_id = self._clean_identity(approver_id, field="approver_id")
        approval_id = self._clean_identity(approval_id, field="approval_id")
        recovery_evidence_id = self._clean_identity(recovery_evidence_id, field="recovery_evidence_id")
        if approval_id in self._approval_ids:
            raise ValueError("approval_id has already been applied")
        policy = self._recovery_policy.get(authority_id)
        if policy is None:
            raise ValueError("recovery quorum policy is not configured")
        approvers, _ = policy
        if approver_id not in approvers:
            raise ValueError("approver_id is not authorized for this authority")
        compromise = self._compromise_by_key.get(compromised_key_id)
        if compromise is None or compromise.authority_id != authority_id:
            raise ValueError("compromised_key_id has no matching compromise record")
        when = self.policy_epoch if effective_epoch is None else effective_epoch
        if when < compromise.compromised_at_epoch:
            raise ValueError("approval cannot precede key compromise")
        for item in self._recovery_approvals.values():
            if (
                item.authority_id == authority_id
                and item.compromised_key_id == compromised_key_id
                and item.replacement_key_id == replacement_key_id
                and item.recovery_evidence_id == recovery_evidence_id
                and item.approver_id == approver_id
            ):
                raise ValueError("approver has already approved this recovery tuple")
        record = RecoveryApprovalV122(
            approval_id=approval_id,
            authority_id=authority_id,
            compromised_key_id=compromised_key_id,
            replacement_key_id=replacement_key_id,
            approver_id=approver_id,
            recovery_evidence_id=recovery_evidence_id,
            effective_epoch=when,
        )
        self._approval_ids.add(approval_id)
        self._recovery_approvals[approval_id] = record
        return record

    def recovery_quorum_count(
        self,
        authority_id: str,
        *,
        compromised_key_id: str,
        replacement_key_id: str,
        recovery_evidence_id: str,
    ) -> int:
        return len({
            item.approver_id
            for item in self._recovery_approvals.values()
            if item.authority_id == authority_id
            and item.compromised_key_id == compromised_key_id
            and item.replacement_key_id == replacement_key_id
            and item.recovery_evidence_id == recovery_evidence_id
        })

    def recover_authority_key(self, authority_id: str, **kwargs):
        authority_id = self._clean_identity(authority_id, field="authority_id")
        policy = self._recovery_policy.get(authority_id)
        if policy is None:
            raise ValueError("recovery quorum policy is not configured")
        _, threshold = policy
        compromised_key_id = kwargs.get("compromised_key_id")
        replacement_key_id = kwargs.get("replacement_key_id")
        recovery_evidence_id = kwargs.get("recovery_evidence_id")
        count = self.recovery_quorum_count(
            authority_id,
            compromised_key_id=compromised_key_id,
            replacement_key_id=replacement_key_id,
            recovery_evidence_id=recovery_evidence_id,
        )
        if count < threshold:
            raise ValueError("recovery quorum threshold is not satisfied")
        return super().recover_authority_key(authority_id, **kwargs)

    def recovery_approvals(self) -> tuple[RecoveryApprovalV122, ...]:
        return tuple(sorted(self._recovery_approvals.values(), key=lambda item: item.approval_id))
