from __future__ import annotations

from dataclasses import dataclass

from .structural_curiosity_v2 import CuriosityProbe


@dataclass(frozen=True, slots=True)
class ActiveInformationIntent:
    """Ephemeral intent to obtain an observation that separates active futures.

    It is deliberately non-semantic and read-only: it does not ask a language
    question, mutate memory, or choose an answer. It only exposes the earliest
    structurally discriminative observation frontier discovered by curiosity.
    """

    active: bool
    mode: str
    target_depth: int | None
    accepted_observations: tuple[str, ...]
    unresolved_branches: int
    reason: str


def derive_active_information_intent(probe: CuriosityProbe) -> ActiveInformationIntent:
    if not probe.needed:
        return ActiveInformationIntent(
            active=False,
            mode="none",
            target_depth=None,
            accepted_observations=(),
            unresolved_branches=probe.unresolved_branches,
            reason=probe.reason,
        )

    if probe.divergence_depth is None or len(probe.alternative_addresses) < 2:
        return ActiveInformationIntent(
            active=False,
            mode="none",
            target_depth=None,
            accepted_observations=(),
            unresolved_branches=probe.unresolved_branches,
            reason="non-discriminative-probe",
        )

    return ActiveInformationIntent(
        active=True,
        mode="await-discriminative-observation",
        target_depth=probe.divergence_depth,
        accepted_observations=probe.alternative_addresses,
        unresolved_branches=probe.unresolved_branches,
        reason="branch-divergence",
    )
