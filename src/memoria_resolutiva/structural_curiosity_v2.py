from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict

from .dynamic_branch_state_v2 import BranchState


@dataclass(frozen=True, slots=True)
class CuriosityProbe:
    """A structural observation that can discriminate active futures.

    This object carries no semantic interpretation. It reports the earliest branch
    depth at which active continuations differ and the alternative addresses that
    would separate the hypotheses if observed.
    """

    needed: bool
    reason: str
    divergence_depth: int | None
    alternative_addresses: tuple[str, ...]
    partitions: tuple[tuple[str, tuple[str, ...]], ...]
    unresolved_branches: int


def derive_curiosity(state: BranchState) -> CuriosityProbe:
    active = state.active
    if not active:
        return CuriosityProbe(False, "no-active-branches", None, (), (), 0)
    if len(active) == 1:
        return CuriosityProbe(False, "single-active-branch", None, (), (), 1)

    max_depth = max((len(branch.remaining_addresses) for branch in active), default=0)
    if max_depth == 0:
        return CuriosityProbe(False, "no-future-addresses", None, (), (), len(active))

    for depth in range(max_depth):
        groups: dict[str, set[str]] = defaultdict(set)
        terminals: set[str] = set()

        for branch in active:
            if depth >= len(branch.remaining_addresses):
                terminals.update(branch.trajectory_ids)
                continue
            address = branch.remaining_addresses[depth]
            groups[address].update(branch.trajectory_ids)

        # A meaningful discriminator exists when at least two distinct outcomes are
        # possible at this depth. Reaching the end of one branch is itself a distinct
        # structural outcome and is represented by the reserved diagnostic marker.
        alternative_count = len(groups) + (1 if terminals else 0)
        if alternative_count < 2:
            continue

        partitions: list[tuple[str, tuple[str, ...]]] = [
            (address, tuple(sorted(ids))) for address, ids in sorted(groups.items())
        ]
        alternatives = list(sorted(groups))
        if terminals:
            partitions.append(("<END>", tuple(sorted(terminals))))
            alternatives.append("<END>")

        return CuriosityProbe(
            True,
            "branch-divergence",
            depth,
            tuple(alternatives),
            tuple(partitions),
            len(active),
        )

    return CuriosityProbe(
        False,
        "branches-structurally-identical-within-horizon",
        None,
        (),
        (),
        len(active),
    )
