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
    """Describe the queried ordered transition without leaking address identity.

    The ordered transition ``left -> right`` must itself have independent support.
    Observing only ``right -> left`` is not evidence for the queried order and
    therefore fails closed.  When both orders are independently supported the
    anonymous relation is bidirectional; otherwise the queried direction is
    forward-only.
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

    # Crucial: support in the opposite direction cannot validate the order that
    # is currently being queried.
    if not forward_supported:
        return None
    if reverse_supported:
        return "bidirectional"
    return "forward-only"


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
    Every component and every adjacent *queried-direction* transition must have
    enough independent trajectory support and remain structurally discriminative;
    otherwise the configuration fails closed.

    Role IDs alone are insufficient when two addresses occupy the same local role:
    A->B and B->A would otherwise collapse to [role, role]. The signature therefore
    also encodes the anonymous directional regime between adjacent roles. Perfectly
    symmetric bidirectional topology remains symmetric; the engine does not invent
    an orientation that is absent from the evidence.
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
