from __future__ import annotations

from dataclasses import dataclass

from .controller_transfer_v124 import ControllerTransferMemoryV124, GuardianControllerTransferV124


@dataclass(frozen=True, slots=True)
class ControllerTransferApprovalV125:
    approval_id: str
    guardian_id: str
    current_controller_id: str
    new_controller_id: str
    approver_id: str
    approver_controller_id: str
    transfer_evidence_id: str
    effective_epoch: int


class ControllerTransferQuorumMemoryV125(ControllerTransferMemoryV124):
    """v1.24 plus an independent quorum gate for guardian-controller transfer.

    Recovery quorum and transfer quorum are deliberately separate policies. Transfer
    approvals are bound to the exact guardian/current-controller/new-controller/
    evidence/epoch tuple and count distinct approver controller domains.
    Cryptographic validation of approvals remains external to the memory core.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._transfer_policy: dict[str, tuple[frozenset[str], int]] = {}
        self._transfer_approvals: dict[str, ControllerTransferApprovalV125] = {}

    def configure_controller_transfer_quorum(
        self, guardian_id: str, *, approver_ids, threshold: int
    ) -> None:
        guardian_id = self._clean_identity(guardian_id, field="guardian_id")
        if self.guardian_controller(guardian_id) is None:
            raise ValueError("guardian must have an initial controller binding")
        cleaned = frozenset(
            self._clean_identity(item, field="approver_id") for item in approver_ids
        )
        if not cleaned:
            raise ValueError("at least one transfer approver is required")
        controllers = []
        for approver in cleaned:
            controller = self.guardian_controller(approver)
            if controller is None:
                raise ValueError("every transfer approver must have a controller binding")
            controllers.append(controller)
        if threshold < 1 or threshold > len(set(controllers)):
            raise ValueError("threshold must be between 1 and independent approver controllers")
        policy = (cleaned, threshold)
        existing = self._transfer_policy.get(guardian_id)
        if existing is not None and existing != policy:
            raise ValueError("controller transfer quorum policy is immutable once configured")
        self._transfer_policy[guardian_id] = policy

    def approve_controller_transfer(
        self,
        guardian_id: str,
        *,
        current_controller_id: str,
        new_controller_id: str,
        approver_id: str,
        approval_id: str,
        transfer_evidence_id: str,
        effective_epoch: int | None = None,
    ) -> ControllerTransferApprovalV125:
        guardian_id = self._clean_identity(guardian_id, field="guardian_id")
        current_controller_id = self._clean_identity(current_controller_id, field="current_controller_id")
        new_controller_id = self._clean_identity(new_controller_id, field="new_controller_id")
        approver_id = self._clean_identity(approver_id, field="approver_id")
        approval_id = self._clean_identity(approval_id, field="approval_id")
        transfer_evidence_id = self._clean_identity(transfer_evidence_id, field="transfer_evidence_id")
        if approval_id in self._transfer_approvals:
            raise ValueError("transfer approval_id has already been applied")
        policy = self._transfer_policy.get(guardian_id)
        if policy is None:
            raise ValueError("controller transfer quorum policy is not configured")
        approvers, _ = policy
        if approver_id not in approvers:
            raise ValueError("approver_id is not authorized for this controller transfer")
        when = self.policy_epoch if effective_epoch is None else effective_epoch
        if when < self.policy_epoch:
            raise ValueError("controller transfer approval cannot be backdated")
        actual = self.guardian_controller_at(guardian_id, epoch=when)
        if actual != current_controller_id:
            raise ValueError("current_controller_id does not own guardian at effective epoch")
        approver_controller = self.guardian_controller_at(approver_id, epoch=when)
        if approver_controller is None:
            raise ValueError("transfer approver has no controller at effective epoch")
        for item in self._transfer_approvals.values():
            if (
                item.guardian_id == guardian_id
                and item.current_controller_id == current_controller_id
                and item.new_controller_id == new_controller_id
                and item.transfer_evidence_id == transfer_evidence_id
                and item.effective_epoch == when
                and item.approver_id == approver_id
            ):
                raise ValueError("approver has already approved this transfer tuple")
        record = ControllerTransferApprovalV125(
            approval_id=approval_id,
            guardian_id=guardian_id,
            current_controller_id=current_controller_id,
            new_controller_id=new_controller_id,
            approver_id=approver_id,
            approver_controller_id=approver_controller,
            transfer_evidence_id=transfer_evidence_id,
            effective_epoch=when,
        )
        self._transfer_approvals[approval_id] = record
        return record

    def controller_transfer_quorum_count(
        self,
        guardian_id: str,
        *,
        current_controller_id: str,
        new_controller_id: str,
        transfer_evidence_id: str,
        effective_epoch: int,
    ) -> int:
        return len({
            item.approver_controller_id
            for item in self._transfer_approvals.values()
            if item.guardian_id == guardian_id
            and item.current_controller_id == current_controller_id
            and item.new_controller_id == new_controller_id
            and item.transfer_evidence_id == transfer_evidence_id
            and item.effective_epoch == effective_epoch
        })

    def transfer_guardian_controller(self, guardian_id: str, **kwargs) -> GuardianControllerTransferV124:
        guardian_id = self._clean_identity(guardian_id, field="guardian_id")
        policy = self._transfer_policy.get(guardian_id)
        if policy is None:
            raise ValueError("controller transfer quorum policy is not configured")
        _, threshold = policy
        when = self.policy_epoch if kwargs.get("effective_epoch") is None else kwargs["effective_epoch"]
        current = self.guardian_controller_at(guardian_id, epoch=when)
        if current is None:
            raise ValueError("guardian must have an initial controller binding")
        count = self.controller_transfer_quorum_count(
            guardian_id,
            current_controller_id=current,
            new_controller_id=kwargs.get("new_controller_id"),
            transfer_evidence_id=kwargs.get("transfer_evidence_id"),
            effective_epoch=when,
        )
        if count < threshold:
            raise ValueError("controller transfer quorum threshold is not satisfied")
        return super().transfer_guardian_controller(guardian_id, **kwargs)

    def controller_transfer_approvals(self) -> tuple[ControllerTransferApprovalV125, ...]:
        return tuple(sorted(self._transfer_approvals.values(), key=lambda item: item.approval_id))
