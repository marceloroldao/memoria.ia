from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.dynamic_branch_state_v2 import BranchState, DynamicBranchStateResolver


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    previous_state: BranchState
    observed_addresses: tuple[str, ...]
    recovered_state: BranchState | None
    recovered: bool
    retrieval_text: str | None


class TrajectoryRecoveryResolver:
    """Re-open retrieval when the current branch state is exhausted.

    Recovery never mutates memory and never joins two stored occurrences. It uses the
    newly observed configuration as a fresh retrieval seed. A failed prediction is
    therefore evidence that the current hypothesis set was insufficient, not that the
    observation or any stored trajectory is false.
    """

    def __init__(self, memory: AddressTrajectoryMemory, *, max_depth: int = 3) -> None:
        self.memory = memory
        self.dynamic = DynamicBranchStateResolver(memory, max_depth=max_depth)

    def recover_text(
        self,
        state: BranchState,
        text: str,
        *,
        max_steps: int = 8,
        candidate_limit: int = 64,
        branch_limit: int = 16,
    ) -> RecoveryResult:
        tokens = self.memory._collapse_immediate_tokens(self.memory.decompose(text))
        addresses = tuple(token.address for token in tokens)
        if not addresses:
            return RecoveryResult(state, (), None, False, None)

        updated = state
        for address in addresses:
            updated = self.dynamic.observe_address(updated, address)
            if updated.exhausted:
                break
        if not updated.exhausted:
            return RecoveryResult(state, addresses, updated, False, None)

        # Fresh retrieval is deliberately based on the new observation only. This
        # avoids stitching an exhausted old occurrence to a new one through a hub.
        recovered = self.dynamic.begin(
            text,
            max_steps=max_steps,
            candidate_limit=candidate_limit,
            branch_limit=branch_limit,
        )
        if recovered.exhausted:
            return RecoveryResult(updated, addresses, None, False, text)
        return RecoveryResult(updated, addresses, recovered, True, text)
