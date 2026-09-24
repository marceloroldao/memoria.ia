from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .evolving_address_state_v2 import AddressStateRevision
from .structural_branch_state_v2 import StructuralBranchStateV2


class TemporalStateOperationV2(str, Enum):
    CURRENT = "current"
    PREVIOUS = "previous"
    HISTORY = "history"
    CHANGE = "change"
    FORWARD = "forward"
    REVERSE = "reverse"


class AddressStateReaderV2(Protocol):
    def current_revision(self, address: int, *, hierarchy_id: str) -> AddressStateRevision | None: ...
    def history(self, address: int, *, hierarchy_id: str) -> tuple[AddressStateRevision, ...]: ...
    def previous_revision(self, revision_id: str) -> AddressStateRevision | None: ...
    def next_revision(self, revision_id: str) -> AddressStateRevision | None: ...


@dataclass(frozen=True, slots=True)
class TemporalStateChangeV2:
    hierarchy_id: str
    address: int
    from_revision_id: str
    to_revision_id: str
    from_sequence: int
    to_sequence: int
    retained_addresses: tuple[int, ...]
    removed_addresses: tuple[int, ...]
    added_addresses: tuple[int, ...]
    trajectory_ids_before: tuple[str, ...]
    trajectory_ids_after: tuple[str, ...]
    provenance_ids_before: tuple[str, ...]
    provenance_ids_after: tuple[str, ...]

    @property
    def state_changed(self) -> bool:
        return bool(self.removed_addresses) or bool(self.added_addresses)

    @property
    def evidence_changed(self) -> bool:
        return (
            self.trajectory_ids_before != self.trajectory_ids_after
            or self.provenance_ids_before != self.provenance_ids_after
        )

    @property
    def changed(self) -> bool:
        return self.state_changed


@dataclass(frozen=True, slots=True)
class TemporalStateResolutionV2:
    hierarchy_id: str
    address: int
    operation: TemporalStateOperationV2
    anchor_revision_id: str | None
    revision: AddressStateRevision | None
    revisions: tuple[AddressStateRevision, ...]
    change: TemporalStateChangeV2 | None
    resolved: bool
    ambiguous: bool
    reason: str
    semantic_projection: bool = False


@dataclass(frozen=True, slots=True)
class TemporalPossibleOutcomeV2:
    kind: str
    address: int | None
    trajectory_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TemporalPossibilityResolutionV2:
    hierarchy_id: str
    seed_addresses: tuple[int, ...]
    observed_addresses: tuple[int, ...]
    outcomes: tuple[TemporalPossibleOutcomeV2, ...]
    resolved_outcome: TemporalPossibleOutcomeV2 | None
    resolved: bool
    ambiguous: bool
    bounded_out: bool
    reason: str
    semantic_projection: bool = False


def _lcs_indices(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    rows = len(left) + 1
    cols = len(right) + 1
    dp = [[0] * cols for _ in range(rows)]
    for i in range(1, rows):
        for j in range(1, cols):
            if left[i - 1] == right[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    i, j = len(left), len(right)
    left_indices: list[int] = []
    right_indices: list[int] = []
    while i > 0 and j > 0:
        if left[i - 1] == right[j - 1]:
            left_indices.append(i - 1)
            right_indices.append(j - 1)
            i -= 1
            j -= 1
        elif dp[i - 1][j] > dp[i][j - 1]:
            i -= 1
        elif dp[i - 1][j] < dp[i][j - 1]:
            j -= 1
        else:
            j -= 1
    left_indices.reverse()
    right_indices.reverse()
    return tuple(left_indices), tuple(right_indices)


def temporal_state_change_v2(before: AddressStateRevision, after: AddressStateRevision) -> TemporalStateChangeV2:
    if before.hierarchy_id != after.hierarchy_id:
        raise ValueError("temporal change requires revisions from one hierarchy")
    if before.address != after.address:
        raise ValueError("temporal change requires revisions of one stable address")
    if after.sequence < before.sequence:
        raise ValueError("temporal change must move forward in sequence")

    left_indices, right_indices = _lcs_indices(before.payload_addresses, after.payload_addresses)
    left_kept = set(left_indices)
    right_kept = set(right_indices)
    retained = tuple(before.payload_addresses[index] for index in left_indices)
    removed = tuple(value for index, value in enumerate(before.payload_addresses) if index not in left_kept)
    added = tuple(value for index, value in enumerate(after.payload_addresses) if index not in right_kept)

    return TemporalStateChangeV2(
        hierarchy_id=before.hierarchy_id,
        address=before.address,
        from_revision_id=before.revision_id,
        to_revision_id=after.revision_id,
        from_sequence=before.sequence,
        to_sequence=after.sequence,
        retained_addresses=retained,
        removed_addresses=removed,
        added_addresses=added,
        trajectory_ids_before=before.trajectory_ids,
        trajectory_ids_after=after.trajectory_ids,
        provenance_ids_before=before.provenance_ids,
        provenance_ids_after=after.provenance_ids,
    )


class TemporalStateResolverV2:
    """Read-only temporal navigation over one stable evolving address.

    The caller supplies an explicit temporal operation. This layer contains no
    natural-language rules. Observed history and possible futures stay separate:
    this resolver navigates admitted revisions only.
    """

    def __init__(self, state: AddressStateReaderV2) -> None:
        self.state = state

    @staticmethod
    def _normalize_operation(operation: TemporalStateOperationV2 | str) -> TemporalStateOperationV2:
        if isinstance(operation, TemporalStateOperationV2):
            return operation
        try:
            return TemporalStateOperationV2(str(operation))
        except ValueError as exc:
            raise ValueError("unsupported temporal state operation") from exc

    def _history(self, address: int, *, hierarchy_id: str) -> tuple[AddressStateRevision, ...]:
        history = self.state.history(int(address), hierarchy_id=hierarchy_id)
        previous_sequence = -1
        for revision in history:
            if revision.address != int(address) or revision.hierarchy_id != hierarchy_id:
                raise ValueError("state reader returned a revision outside the requested address")
            if revision.sequence < previous_sequence:
                raise ValueError("state reader returned non-monotonic temporal history")
            previous_sequence = revision.sequence
        return history

    @staticmethod
    def _find_anchor(history: tuple[AddressStateRevision, ...], revision_id: str | None) -> AddressStateRevision | None:
        if revision_id is None:
            return None if not history else history[-1]
        target = str(revision_id).strip()
        if not target:
            raise ValueError("anchor_revision_id must be non-empty when supplied")
        for revision in history:
            if revision.revision_id == target:
                return revision
        raise LookupError("anchor revision is not part of the requested stable address")

    def resolve(
        self,
        address: int,
        *,
        hierarchy_id: str,
        operation: TemporalStateOperationV2 | str,
        anchor_revision_id: str | None = None,
    ) -> TemporalStateResolutionV2:
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        stable_address = int(address)
        if stable_address < 0:
            raise ValueError("address must be >= 0")
        op = self._normalize_operation(operation)
        history = self._history(stable_address, hierarchy_id=hierarchy)

        if not history:
            return TemporalStateResolutionV2(
                hierarchy, stable_address, op, anchor_revision_id, None, (), None,
                False, False, "no-state-history",
            )

        if op is TemporalStateOperationV2.CURRENT:
            if anchor_revision_id is not None:
                raise ValueError("current operation does not accept anchor_revision_id")
            current = history[-1]
            return TemporalStateResolutionV2(
                hierarchy, stable_address, op, None, current, (current,), None,
                True, False, "current-revision",
            )

        if op is TemporalStateOperationV2.HISTORY:
            if anchor_revision_id is not None:
                raise ValueError("history operation does not accept anchor_revision_id")
            return TemporalStateResolutionV2(
                hierarchy, stable_address, op, None, history[-1], history, None,
                True, False, "complete-observed-history",
            )

        anchor = self._find_anchor(history, anchor_revision_id)
        assert anchor is not None

        if op is TemporalStateOperationV2.PREVIOUS:
            if anchor_revision_id is not None:
                raise ValueError("previous operation always refers to the current revision")
            previous = self.state.previous_revision(anchor.revision_id)
            return TemporalStateResolutionV2(
                hierarchy, stable_address, op, anchor.revision_id, previous,
                () if previous is None else (previous,), None,
                previous is not None, False,
                "no-previous-revision" if previous is None else "previous-revision",
            )

        if op is TemporalStateOperationV2.REVERSE:
            previous = self.state.previous_revision(anchor.revision_id)
            return TemporalStateResolutionV2(
                hierarchy, stable_address, op, anchor.revision_id, previous,
                () if previous is None else (previous,), None,
                previous is not None, False,
                "reverse-boundary" if previous is None else "reverse-neighbor",
            )

        if op is TemporalStateOperationV2.FORWARD:
            following = self.state.next_revision(anchor.revision_id)
            return TemporalStateResolutionV2(
                hierarchy, stable_address, op, anchor.revision_id, following,
                () if following is None else (following,), None,
                following is not None, False,
                "forward-boundary" if following is None else "forward-neighbor",
            )

        if op is TemporalStateOperationV2.CHANGE:
            previous = self.state.previous_revision(anchor.revision_id)
            if previous is None:
                return TemporalStateResolutionV2(
                    hierarchy, stable_address, op, anchor.revision_id, anchor,
                    (anchor,), None, False, False, "no-previous-revision-for-change",
                )
            change = temporal_state_change_v2(previous, anchor)
            return TemporalStateResolutionV2(
                hierarchy, stable_address, op, anchor.revision_id, anchor,
                (previous, anchor), change, True, False,
                "observed-state-change" if change.state_changed else "observed-state-stable",
            )

        raise AssertionError("unreachable temporal operation")


def temporal_possibilities_from_branch_state(state: StructuralBranchStateV2) -> TemporalPossibilityResolutionV2:
    """Expose R4 possible futures without admitting them into observed history."""
    if state.bounded_out:
        return TemporalPossibilityResolutionV2(
            state.hierarchy_id, state.seed_addresses, state.observed_addresses,
            (), None, False, True, True, "branch-state-bounded-out",
        )

    grouped: dict[int, set[str]] = {}
    terminal_ids: set[str] = set(state.terminal_trajectory_ids)

    for branch in state.active:
        if branch.remaining_addresses:
            next_address = int(branch.remaining_addresses[0])
            grouped.setdefault(next_address, set()).update(branch.trajectory_ids)
        else:
            terminal_ids.update(branch.trajectory_ids)

    outcomes: list[TemporalPossibleOutcomeV2] = [
        TemporalPossibleOutcomeV2(
            kind="next-address",
            address=address,
            trajectory_ids=tuple(sorted(trajectory_ids)),
        )
        for address, trajectory_ids in sorted(grouped.items())
    ]
    if terminal_ids:
        outcomes.append(
            TemporalPossibleOutcomeV2(
                kind="terminal",
                address=None,
                trajectory_ids=tuple(sorted(terminal_ids)),
            )
        )

    visible = tuple(outcomes)
    if not visible:
        return TemporalPossibilityResolutionV2(
            state.hierarchy_id, state.seed_addresses, state.observed_addresses,
            (), None, False, False, False, "no-observed-compatible-future",
        )

    if len(visible) == 1:
        return TemporalPossibilityResolutionV2(
            state.hierarchy_id, state.seed_addresses, state.observed_addresses,
            visible, visible[0], True, False, False,
            "single-terminal-outcome" if visible[0].kind == "terminal" else "single-next-address",
        )

    return TemporalPossibilityResolutionV2(
        state.hierarchy_id, state.seed_addresses, state.observed_addresses,
        visible, None, False, True, False, "competing-temporal-outcomes",
    )
