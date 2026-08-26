from __future__ import annotations

from dataclasses import dataclass

from .guardian_independence_v123 import GuardianIndependenceMemoryV123


@dataclass(frozen=True, slots=True)
class GuardianControllerTransferV124:
    transfer_id: str
    guardian_id: str
    previous_controller_id: str
    new_controller_id: str
    transfer_evidence_id: str
    effective_epoch: int


class ControllerTransferMemoryV124(GuardianIndependenceMemoryV123):
    """v1.23 plus append-only temporal transfer of guardian control.

    Controller identity is resolved at a logical policy epoch. A transfer never
    rewrites historical approvals: recovery quorum counts the controller that owned
    each guardian when that approval was recorded. Cryptographic/legal validation
    of transfer evidence remains outside the memory core.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._controller_history: dict[str, list[tuple[int, str]]] = {}
        self._controller_transfers: dict[str, GuardianControllerTransferV124] = {}
        self._transfer_evidence_ids: set[str] = set()

    def bind_guardian_controller(self, guardian_id: str, *, controller_id: str) -> None:
        guardian_id = self._clean_identity(guardian_id, field="guardian_id")
        controller_id = self._clean_identity(controller_id, field="controller_id")
        history = self._controller_history.get(guardian_id)
        if history:
            if history[0][1] != controller_id:
                raise ValueError("guardian already has an initial controller binding")
            return
        self._controller_history[guardian_id] = [(self.policy_epoch, controller_id)]
        self._guardian_controller[guardian_id] = controller_id

    def guardian_controller_at(self, guardian_id: str, *, epoch: int | None = None) -> str | None:
        guardian_id = self._clean_identity(guardian_id, field="guardian_id")
        at = self.policy_epoch if epoch is None else epoch
        if at < 0:
            raise ValueError("epoch must be >= 0")
        history = self._controller_history.get(guardian_id, ())
        active = [item for item in history if item[0] <= at]
        if not active:
            return None
        active.sort(key=lambda item: item[0])
        return active[-1][1]

    def guardian_controller(self, guardian_id: str) -> str | None:
        return self.guardian_controller_at(guardian_id)

    def transfer_guardian_controller(
        self,
        guardian_id: str,
        *,
        new_controller_id: str,
        authorized_by_controller_id: str,
        transfer_id: str,
        transfer_evidence_id: str,
        effective_epoch: int | None = None,
    ) -> GuardianControllerTransferV124:
        guardian_id = self._clean_identity(guardian_id, field="guardian_id")
        new_controller_id = self._clean_identity(new_controller_id, field="new_controller_id")
        authorized_by_controller_id = self._clean_identity(
            authorized_by_controller_id, field="authorized_by_controller_id"
        )
        transfer_id = self._clean_identity(transfer_id, field="transfer_id")
        transfer_evidence_id = self._clean_identity(
            transfer_evidence_id, field="transfer_evidence_id"
        )
        if transfer_id in self._controller_transfers:
            raise ValueError("transfer_id has already been applied")
        if transfer_evidence_id in self._transfer_evidence_ids:
            raise ValueError("transfer_evidence_id has already been applied")
        when = self.policy_epoch if effective_epoch is None else effective_epoch
        if when < self.policy_epoch:
            raise ValueError("controller transfer cannot be backdated")
        previous = self.guardian_controller_at(guardian_id, epoch=when)
        if previous is None:
            raise ValueError("guardian must have an initial controller binding")
        if previous != authorized_by_controller_id:
            raise ValueError("controller transfer must be authorized by current controller")
        if previous == new_controller_id:
            raise ValueError("new controller must differ from current controller")
        history = self._controller_history[guardian_id]
        if any(epoch == when for epoch, _ in history):
            raise ValueError("only one controller state is allowed per guardian and epoch")
        record = GuardianControllerTransferV124(
            transfer_id=transfer_id,
            guardian_id=guardian_id,
            previous_controller_id=previous,
            new_controller_id=new_controller_id,
            transfer_evidence_id=transfer_evidence_id,
            effective_epoch=when,
        )
        history.append((when, new_controller_id))
        history.sort(key=lambda item: item[0])
        self._guardian_controller[guardian_id] = self.guardian_controller_at(guardian_id) or new_controller_id
        self._controller_transfers[transfer_id] = record
        self._transfer_evidence_ids.add(transfer_evidence_id)
        return record

    def configure_recovery_quorum(self, authority_id: str, *, approver_ids, threshold: int) -> None:
        cleaned = [self._clean_identity(item, field="approver_id") for item in approver_ids]
        controllers = []
        for item in cleaned:
            controller = self.guardian_controller_at(item)
            if controller is None:
                raise ValueError("every recovery approver must have a controller binding")
            controllers.append(controller)
        if threshold > len(set(controllers)):
            raise ValueError("threshold cannot exceed number of independent controllers")
        # Call v1.22 directly because v1.23 assumes immutable current bindings.
        super(GuardianIndependenceMemoryV123, self).configure_recovery_quorum(
            authority_id, approver_ids=cleaned, threshold=threshold
        )

    def recovery_quorum_count(
        self,
        authority_id: str,
        *,
        compromised_key_id: str,
        replacement_key_id: str,
        recovery_evidence_id: str,
    ) -> int:
        controllers = set()
        for item in self._recovery_approvals.values():
            if (
                item.authority_id == authority_id
                and item.compromised_key_id == compromised_key_id
                and item.replacement_key_id == replacement_key_id
                and item.recovery_evidence_id == recovery_evidence_id
            ):
                controller = self.guardian_controller_at(
                    item.approver_id, epoch=item.effective_epoch
                )
                if controller is not None:
                    controllers.add(controller)
        return len(controllers)

    def guardian_controller_transfers(self) -> tuple[GuardianControllerTransferV124, ...]:
        return tuple(sorted(self._controller_transfers.values(), key=lambda item: item.transfer_id))
