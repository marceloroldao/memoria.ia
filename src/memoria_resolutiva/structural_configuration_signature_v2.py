from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from typing import Iterable

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


def configuration_role_signature(
    memory: AddressTrajectoryMemory,
    addresses: tuple[str, ...],
    *,
    min_independent_lineages: int = 2,
    max_neighbor_diversity: int = 32,
) -> StructuralConfigurationSignature:
    """Describe a current configuration by ordered anonymous topological roles.

    Literal addresses are used only to locate each address in the observed memory.
    They are never included in the resulting signature. Every component must have
    enough independent trajectory support and remain structurally discriminative;
    otherwise the configuration fails closed.
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

    ordered = tuple(role_ids)
    return StructuralConfigurationSignature(
        _digest(tuple(f"role:{role_id}" for role_id in ordered)),
        ordered,
        True,
        "supported",
    )
