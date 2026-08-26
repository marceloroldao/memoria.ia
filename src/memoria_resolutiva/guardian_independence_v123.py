from __future__ import annotations

from .recovery_quorum_v122 import RecoveryQuorumMemoryV122


class GuardianIndependenceMemoryV123(RecoveryQuorumMemoryV122):
    """v1.22 plus independence domains for recovery guardians.

    Distinct guardian IDs do not necessarily represent independent control. Each
    authorized guardian must be bound to an immutable controller/domain ID, and
    quorum counts distinct controller IDs rather than raw guardian IDs.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._guardian_controller: dict[str, str] = {}

    def bind_guardian_controller(self, guardian_id: str, *, controller_id: str) -> None:
        guardian_id = self._clean_identity(guardian_id, field="guardian_id")
        controller_id = self._clean_identity(controller_id, field="controller_id")
        existing = self._guardian_controller.get(guardian_id)
        if existing is not None and existing != controller_id:
            raise ValueError("guardian controller binding is immutable")
        self._guardian_controller[guardian_id] = controller_id

    def configure_recovery_quorum(self, authority_id: str, *, approver_ids, threshold: int) -> None:
        cleaned = [self._clean_identity(item, field="approver_id") for item in approver_ids]
        missing = [item for item in cleaned if item not in self._guardian_controller]
        if missing:
            raise ValueError("every recovery approver must have a controller binding")
        controllers = {self._guardian_controller[item] for item in cleaned}
        if threshold > len(controllers):
            raise ValueError("threshold cannot exceed number of independent controllers")
        super().configure_recovery_quorum(authority_id, approver_ids=cleaned, threshold=threshold)

    def recovery_quorum_count(
        self,
        authority_id: str,
        *,
        compromised_key_id: str,
        replacement_key_id: str,
        recovery_evidence_id: str,
    ) -> int:
        controllers = {
            self._guardian_controller[item.approver_id]
            for item in self._recovery_approvals.values()
            if item.authority_id == authority_id
            and item.compromised_key_id == compromised_key_id
            and item.replacement_key_id == replacement_key_id
            and item.recovery_evidence_id == recovery_evidence_id
            and item.approver_id in self._guardian_controller
        }
        return len(controllers)

    def guardian_controller(self, guardian_id: str) -> str | None:
        guardian_id = self._clean_identity(guardian_id, field="guardian_id")
        return self._guardian_controller.get(guardian_id)
