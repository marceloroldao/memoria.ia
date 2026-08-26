from __future__ import annotations

from dataclasses import dataclass

from .controller_transfer_quorum_v125 import (
    ControllerTransferApprovalV125,
    ControllerTransferQuorumMemoryV125,
)


@dataclass(frozen=True, slots=True)
class ControllerTransferApprovalRevocationV126:
    revocation_id: str
    approval_id: str
    guardian_id: str
    approver_id: str
    transfer_evidence_id: str
    effective_epoch: int
    revoked_epoch: int


class ControllerTransferRevocationMemoryV126(ControllerTransferQuorumMemoryV125):
    """v1.25 plus explicit revocation of controller-transfer approvals.

    Revocation is conservative and final for the exact approval record:
    - only the original approver may revoke its approval;
    - revocation must happen no later than the approval's effective epoch;
    - revocation identifiers are replay-protected;
    - a revoked approval no longer contributes to transfer quorum;
    - the inherited v1.25 duplicate-approval rule prevents silently replacing a
      revoked approval for the same approver/transfer tuple.

    Cryptographic validation remains external to the memory core.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._transfer_approval_revocations: dict[
            str, ControllerTransferApprovalRevocationV126
        ] = {}
        self._revoked_transfer_approval_ids: set[str] = set()

    def revoke_controller_transfer_approval(
        self,
        approval_id: str,
        *,
        approver_id: str,
        revocation_id: str,
    ) -> ControllerTransferApprovalRevocationV126:
        approval_id = self._clean_identity(approval_id, field="approval_id")
        approver_id = self._clean_identity(approver_id, field="approver_id")
        revocation_id = self._clean_identity(revocation_id, field="revocation_id")

        if revocation_id in self._transfer_approval_revocations:
            raise ValueError("transfer approval revocation_id has already been applied")

        approval = self._transfer_approvals.get(approval_id)
        if approval is None:
            raise ValueError("controller transfer approval does not exist")
        if approval.approver_id != approver_id:
            raise ValueError("only the original approver may revoke this transfer approval")
        if approval_id in self._revoked_transfer_approval_ids:
            raise ValueError("controller transfer approval has already been revoked")
        if self.policy_epoch > approval.effective_epoch:
            raise ValueError("controller transfer approval cannot be revoked after effective epoch")

        record = ControllerTransferApprovalRevocationV126(
            revocation_id=revocation_id,
            approval_id=approval_id,
            guardian_id=approval.guardian_id,
            approver_id=approval.approver_id,
            transfer_evidence_id=approval.transfer_evidence_id,
            effective_epoch=approval.effective_epoch,
            revoked_epoch=self.policy_epoch,
        )
        self._transfer_approval_revocations[revocation_id] = record
        self._revoked_transfer_approval_ids.add(approval_id)
        return record

    def controller_transfer_approval_is_revoked(self, approval_id: str) -> bool:
        approval_id = self._clean_identity(approval_id, field="approval_id")
        return approval_id in self._revoked_transfer_approval_ids

    def controller_transfer_quorum_count(
        self,
        guardian_id: str,
        *,
        current_controller_id: str,
        new_controller_id: str,
        transfer_evidence_id: str,
        effective_epoch: int,
    ) -> int:
        return len(
            {
                item.approver_controller_id
                for item in self._transfer_approvals.values()
                if item.approval_id not in self._revoked_transfer_approval_ids
                and item.guardian_id == guardian_id
                and item.current_controller_id == current_controller_id
                and item.new_controller_id == new_controller_id
                and item.transfer_evidence_id == transfer_evidence_id
                and item.effective_epoch == effective_epoch
            }
        )

    def controller_transfer_approval_revocations(
        self,
    ) -> tuple[ControllerTransferApprovalRevocationV126, ...]:
        return tuple(
            sorted(
                self._transfer_approval_revocations.values(),
                key=lambda item: item.revocation_id,
            )
        )
