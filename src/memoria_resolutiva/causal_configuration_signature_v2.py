from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b

from .address_trajectory_v2 import AddressTrajectoryMemory


def _digest(parts: tuple[str, ...]) -> str:
    payload = ("memoria.causal-configuration.v2\x00" + "\x1f".join(parts)).encode("utf-8")
    return "ccfg2:" + blake2b(payload, digest_size=16).hexdigest()


@dataclass(frozen=True, slots=True)
class CausalConfigurationSignature:
    signature_id: str | None
    role_ids: tuple[str, ...]
    supported: bool
    reason: str


def _ordered_transition_support(
    memory: AddressTrajectoryMemory,
    left: str,
    right: str,
    *,
    min_independent_lineages: int,
) -> tuple[bool, bool]:
    forward: set[str] = set()
    reverse: set[str] = set()
    for trajectory in memory.snapshot():
        pairs = tuple(zip(trajectory.addresses, trajectory.addresses[1:]))
        if (left, right) in pairs:
            forward.add(trajectory.trajectory_id)
        if (right, left) in pairs:
            reverse.add(trajectory.trajectory_id)
    return (
        len(forward) >= min_independent_lineages,
        len(reverse) >= min_independent_lineages,
    )


def _causal_role_id(
    memory: AddressTrajectoryMemory,
    address: str,
    *,
    min_independent_lineages: int,
    max_predecessor_diversity: int,
) -> tuple[str | None, str]:
    """Describe only topology available at the instant ``address`` is observed.

    Successors and distance-to-end are deliberately excluded.  This prevents
    future leakage when a stored trajectory is used to forecast a frontier whose
    continuation is not yet observed.
    """
    lineages: set[str] = set()
    predecessor_lineages: dict[str, set[str]] = {}
    causal_positions: set[int] = set()
    occurrence_count = 0

    for trajectory in memory.snapshot():
        for index, observed in enumerate(trajectory.addresses):
            if observed != address:
                continue
            occurrence_count += 1
            lineages.add(trajectory.trajectory_id)
            causal_positions.add(index)
            predecessor = trajectory.addresses[index - 1] if index > 0 else "<START>"
            predecessor_lineages.setdefault(predecessor, set()).add(trajectory.trajectory_id)

    if occurrence_count == 0:
        return None, "unseen-address"
    if len(lineages) < min_independent_lineages:
        return None, "insufficient-independent-support"
    if len(predecessor_lineages) > max_predecessor_diversity:
        return None, "non-discriminative-causal-role"

    # Concrete predecessor identities are discarded.  Only anonymous incidence
    # geometry that existed before/at the focus survives in the fingerprint.
    predecessor_support_spectrum = tuple(sorted(len(items) for items in predecessor_lineages.values()))
    parts = (
        tuple(f"position:{value}" for value in sorted(causal_positions))
        + (f"pred-div:{len(predecessor_lineages)}",)
        + tuple(f"pred-support:{value}" for value in predecessor_support_spectrum)
    )
    return "cr2:" + blake2b(("\x1f".join(parts)).encode("utf-8"), digest_size=16).hexdigest(), "supported"


def causal_configuration_signature(
    memory: AddressTrajectoryMemory,
    addresses: tuple[str, ...],
    *,
    min_independent_lineages: int = 2,
    max_predecessor_diversity: int = 32,
) -> CausalConfigurationSignature:
    """Anonymous ordered signature built without information from the future.

    This is the forecasting counterpart of the full structural configuration
    signature.  It keeps only evidence observable up to the current frontier and
    therefore can compare a known trajectory prefix with a held-out frontier
    without leaking the known continuation into the comparison.
    """
    if not addresses:
        return CausalConfigurationSignature(None, (), False, "empty-configuration")
    if min_independent_lineages < 1:
        raise ValueError("min_independent_lineages must be >= 1")

    role_ids: list[str] = []
    for address in addresses:
        role_id, reason = _causal_role_id(
            memory,
            address,
            min_independent_lineages=min_independent_lineages,
            max_predecessor_diversity=max_predecessor_diversity,
        )
        if role_id is None:
            return CausalConfigurationSignature(None, tuple(role_ids), False, reason)
        role_ids.append(role_id)

    transition_modes: list[str] = []
    for left, right in zip(addresses, addresses[1:]):
        forward, reverse = _ordered_transition_support(
            memory,
            left,
            right,
            min_independent_lineages=min_independent_lineages,
        )
        if not forward:
            return CausalConfigurationSignature(
                None,
                tuple(role_ids),
                False,
                "insufficient-transition-support",
            )
        transition_modes.append("bidirectional" if reverse else "forward-only")

    parts: list[str] = []
    for index, role_id in enumerate(role_ids):
        parts.append(f"role:{index}:{role_id}")
        if index < len(transition_modes):
            parts.append(f"transition:{index}:{transition_modes[index]}")

    return CausalConfigurationSignature(
        _digest(tuple(parts)),
        tuple(role_ids),
        True,
        "supported",
    )
