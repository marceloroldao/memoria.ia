from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b

from .address_trajectory_v2 import AddressTrajectoryMemory
from .structural_role_abstraction_v2 import build_role_profile
from .structural_witness_discovery_v2 import TrajectoryOccurrence


def _digest(parts: tuple[str, ...]) -> str:
    payload = ("memoria.structural-configuration.v2\x00" + "\x1f".join(parts)).encode("utf-8")
    return "scfg2:" + blake2b(payload, digest_size=16).hexdigest()


@dataclass(frozen=True, slots=True)
class StructuralConfigurationSignature:
    signature_id: str | None
    role_ids: tuple[str, ...]
    supported: bool
    reason: str


def _transition_mode(
    memory: AddressTrajectoryMemory,
    left: str,
    right: str,
    *,
    min_independent_lineages: int,
) -> str | None:
    """Return an anonymous directional relation between two observed roles.

    Literal addresses are used only to count whether the ordered transition is
    independently observed. The returned mode contains no address identity or
    scalar weight. It distinguishes forward-only, reverse-only and bidirectional
    topology, which is necessary when two concrete addresses occupy the same
    anonymous local role.
    """
    forward_lineages: set[str] = set()
    reverse_lineages: set[str] = set()

    for trajectory in memory.snapshot():
        pairs = tuple(zip(trajectory.addresses, trajectory.addresses[1:]))
        if (left, right) in pairs:
            forward_lineages.add(trajectory.trajectory_id)
        if (right, left) in pairs:
            reverse_lineages.add(trajectory.trajectory_id)

    forward_supported = len(forward_lineages) >= min_independent_lineages
    reverse_supported = len(reverse_lineages) >= min_independent_lineages

    if forward_supported and reverse_supported:
        return "bidirectional"
    if forward_supported:
        return "forward-only"
    if reverse_supported:
        return "reverse-only"
    return None


def configuration_role_signature(
    memory: AddressTrajectoryMemory,
    addresses: tuple[str, ...],
    *,
    min_independent_lineages: int = 2,
    max_neighbor_diversity: int = 32,
) -> StructuralConfigurationSignature:
    """Describe a current configuration by ordered anonymous topological roles.

    Literal addresses are used only to locate each address and its observed
    transitions in memory. They are never included in the resulting signature.
    Every component and every adjacent transition must have enough independent
    trajectory support and remain structurally discriminative; otherwise the
    configuration fails closed.

    Role IDs alone are insufficient when two addresses occupy the same local role:
    A->B and B->A would otherwise collapse to [role, role]. The signature therefore
    also encodes the anonymous *directional transition mode* between adjacent roles.
    """
    if not addresses:
        return StructuralConfigurationSignature(None, (), False, "empty-configuration")
    if min_independent_lineages < 1:
        raise ValueError("min_independent_lineages must be >= 1")

    occurrences = tuple(
        TrajectoryOccurrence(
            trajectory=trajectory,
            lineage_id=trajectory.trajectory_id,
            occurrence_id=trajectory.trajectory_id,
        )
        for trajectory in memory.snapshot()
    )

    role_ids: list[str] = []
    for address in addresses:
        profile = build_role_profile(
            occurrences,
            address,
            max_neighbor_diversity=max_neighbor_diversity,
        )
        if profile.occurrence_count == 0:
            return StructuralConfigurationSignature(None, tuple(role_ids), False, "unseen-address")
        if not profile.discriminative:
            return StructuralConfigurationSignature(None, tuple(role_ids), False, "non-discriminative-role")
        if profile.independent_lineages < min_independent_lineages:
            return StructuralConfigurationSignature(None, tuple(role_ids), False, "insufficient-independent-support")
        role_ids.append(profile.role_id)

    transition_modes: list[str] = []
    for left, right in zip(addresses, addresses[1:]):
        mode = _transition_mode(
            memory,
            left,
            right,
            min_independent_lineages=min_independent_lineages,
        )
        if mode is None:
            return StructuralConfigurationSignature(
                None,
                tuple(role_ids),
                False,
                "insufficient-transition-support",
            )
        transition_modes.append(mode)

    ordered = tuple(role_ids)
    digest_parts: list[str] = []
    for index, role_id in enumerate(ordered):
        digest_parts.append(f"role:{index}:{role_id}")
        if index < len(transition_modes):
            digest_parts.append(f"transition:{index}:{transition_modes[index]}")

    return StructuralConfigurationSignature(
        _digest(tuple(digest_parts)),
        ordered,
        True,
        "supported",
    )
