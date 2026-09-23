from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from .structural_density_v2 import StructuralDensityEngineV2, StructuralDensityProfileV2
from .structural_rollout_v2 import StructuralFrontierHypothesisV2, StructuralRolloutResolverV2
from .structural_trajectory_v2 import StructuralTrajectoryIndex


class StructuralAssociationReader(Protocol):
    def association(
        self,
        hierarchy_id: str,
        source: int,
        target: int,
        *,
        channel: str | None = None,
    ) -> float: ...


@dataclass(frozen=True, slots=True)
class AssociationChannelEvidenceV2:
    channel: str
    supported_query_addresses: int
    total_mass: float
    per_source_mass: tuple[tuple[int, float], ...]


@dataclass(frozen=True, slots=True)
class StructuralAttractorEvidenceV2:
    trajectory_support: int
    matched_address_count: int
    supporting_depth_count: int
    within: AssociationChannelEvidenceV2
    temporal: AssociationChannelEvidenceV2

    @property
    def discrete_dimensions(self) -> tuple[int, int, int, int]:
        # Hierarchy depth is diagnostic only. A strongly recurrent pattern may
        # collapse into a higher composition and therefore appear at fewer derived
        # depths. Treating depth count as attractor strength would let the derived
        # representation contradict the atomic evidence it was built from.
        return (
            self.trajectory_support,
            self.matched_address_count,
            self.within.supported_query_addresses,
            self.temporal.supported_query_addresses,
        )

    @property
    def continuous_dimensions(self) -> tuple[float, float]:
        return (
            self.within.total_mass,
            self.temporal.total_mass,
        )


@dataclass(frozen=True, slots=True)
class StructuralAttractorCandidateV2:
    address: int
    trajectory_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    evidence: StructuralAttractorEvidenceV2
    density: StructuralDensityProfileV2 | None
    dominated_by: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class StructuralAttractorResolutionV2:
    hierarchy_id: str
    query_addresses: tuple[int, ...]
    candidates: tuple[StructuralAttractorCandidateV2, ...]
    pareto_frontier: tuple[int, ...]
    terminal_trajectory_ids: tuple[str, ...]
    resolved_address: int | None
    resolved: bool
    ambiguous: bool
    terminal: bool
    bounded_out: bool
    reason: str
    semantic_projection: bool = False


class StructuralAttractorResolverV2:
    """Conservative structural attractor selection without scalar score mixing.

    R5 deliberately does not calculate:

        a*x + b*y + c*z

    across heterogeneous evidence channels. Instead, each next-address candidate
    exposes an auditable evidence vector. Candidate A dominates B only when A is
    no worse on every active structural dimension and strictly better on at least
    one. Crossed evidence remains ambiguous.

    The continuous association field contributes its already accumulated/decayed
    mass independently in the within-event and temporal channels. Topological
    density is diagnostic only and cannot make a candidate win.
    """

    def __init__(
        self,
        trajectories: StructuralTrajectoryIndex,
        *,
        association_field: StructuralAssociationReader | None = None,
        max_depth: int = 3,
        mass_epsilon: float = 1e-12,
    ) -> None:
        if mass_epsilon < 0.0 or not isfinite(mass_epsilon):
            raise ValueError("mass_epsilon must be finite and >= 0")
        self.trajectories = trajectories
        self.association_field = association_field
        self.mass_epsilon = float(mass_epsilon)
        self.rollout = StructuralRolloutResolverV2(
            trajectories,
            max_depth=max_depth,
        )
        self.density = StructuralDensityEngineV2(trajectories)

    @staticmethod
    def _collapse(addresses) -> tuple[int, ...]:
        output: list[int] = []
        current: int | None = None
        for raw in addresses:
            value = int(raw)
            if value < 0:
                raise ValueError("structural addresses must be >= 0")
            if current == value:
                continue
            output.append(value)
            current = value
        return tuple(output)

    def _association_evidence(
        self,
        query: tuple[int, ...],
        *,
        target: int,
        hierarchy_id: str,
        channel: str,
    ) -> AssociationChannelEvidenceV2:
        if self.association_field is None:
            return AssociationChannelEvidenceV2(channel, 0, 0.0, ())

        per_source: list[tuple[int, float]] = []
        total = 0.0
        supported = 0
        for source in tuple(dict.fromkeys(query)):
            value = float(
                self.association_field.association(
                    hierarchy_id,
                    source,
                    target,
                    channel=channel,
                )
            )
            if not isfinite(value) or value < 0.0:
                raise ValueError("structural association mass must be finite and >= 0")
            per_source.append((source, value))
            total += value
            if value > self.mass_epsilon:
                supported += 1
        return AssociationChannelEvidenceV2(
            channel=channel,
            supported_query_addresses=supported,
            total_mass=total,
            per_source_mass=tuple(per_source),
        )

    def _candidate(
        self,
        hypothesis: StructuralFrontierHypothesisV2,
        *,
        query: tuple[int, ...],
        hierarchy_id: str,
    ) -> StructuralAttractorCandidateV2:
        by_id = {
            item.trajectory_id: item
            for item in self.trajectories.snapshot()
            if item.hierarchy_id == hierarchy_id
        }
        source_ids = tuple(
            sorted(
                {
                    by_id[trajectory_id].source_id
                    for trajectory_id in hypothesis.trajectory_ids
                    if trajectory_id in by_id
                }
            )
        )
        within = self._association_evidence(
            query,
            target=hypothesis.address,
            hierarchy_id=hierarchy_id,
            channel="within",
        )
        temporal = self._association_evidence(
            query,
            target=hypothesis.address,
            hierarchy_id=hierarchy_id,
            channel="temporal",
        )
        return StructuralAttractorCandidateV2(
            address=hypothesis.address,
            trajectory_ids=hypothesis.trajectory_ids,
            source_ids=source_ids,
            evidence=StructuralAttractorEvidenceV2(
                trajectory_support=len(hypothesis.trajectory_ids),
                matched_address_count=len(hypothesis.matched_addresses),
                supporting_depth_count=len(hypothesis.supporting_depths),
                within=within,
                temporal=temporal,
            ),
            density=self.density.profile(
                hypothesis.address,
                hierarchy_id=hierarchy_id,
            ),
        )

    def _dominates(
        self,
        left: StructuralAttractorCandidateV2,
        right: StructuralAttractorCandidateV2,
    ) -> bool:
        left_discrete = left.evidence.discrete_dimensions
        right_discrete = right.evidence.discrete_dimensions
        if any(a < b for a, b in zip(left_discrete, right_discrete)):
            return False

        left_cont = left.evidence.continuous_dimensions
        right_cont = right.evidence.continuous_dimensions
        if any(
            a + self.mass_epsilon < b
            for a, b in zip(left_cont, right_cont)
        ):
            return False

        discrete_strict = any(a > b for a, b in zip(left_discrete, right_discrete))
        continuous_strict = any(
            a > b + self.mass_epsilon
            for a, b in zip(left_cont, right_cont)
        )
        return discrete_strict or continuous_strict

    def resolve_addresses(
        self,
        addresses,
        *,
        hierarchy_id: str,
        candidate_limit: int = 64,
        branch_limit: int = 16,
    ) -> StructuralAttractorResolutionV2:
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        query = self._collapse(addresses)
        if not query:
            raise ValueError("query must contain at least one structural address")

        frontier = self.rollout.frontier_addresses(
            query,
            hierarchy_id=hierarchy,
            candidate_limit=candidate_limit,
            branch_limit=branch_limit,
        )
        if frontier.bounded_out:
            return StructuralAttractorResolutionV2(
                hierarchy,
                query,
                (),
                (),
                frontier.terminal_trajectory_ids,
                None,
                False,
                True,
                False,
                True,
                frontier.reason,
            )

        candidates = tuple(
            self._candidate(
                hypothesis,
                query=query,
                hierarchy_id=hierarchy,
            )
            for hypothesis in frontier.hypotheses
        )

        if not candidates:
            if frontier.terminal_trajectory_ids:
                return StructuralAttractorResolutionV2(
                    hierarchy,
                    query,
                    (),
                    (),
                    frontier.terminal_trajectory_ids,
                    None,
                    False,
                    False,
                    True,
                    False,
                    "terminal-attractor-region",
                )
            return StructuralAttractorResolutionV2(
                hierarchy,
                query,
                (),
                (),
                (),
                None,
                False,
                False,
                False,
                False,
                "no-attractor-candidate",
            )

        # R5 deliberately refuses to compare an observed terminal outcome against
        # a concrete next address using fabricated numerical values for "nothing".
        if frontier.terminal_trajectory_ids:
            return StructuralAttractorResolutionV2(
                hierarchy,
                query,
                candidates,
                tuple(candidate.address for candidate in candidates),
                frontier.terminal_trajectory_ids,
                None,
                False,
                True,
                False,
                False,
                "terminal-competes-with-forward-attractor",
            )

        dominated_by: dict[int, list[int]] = {candidate.address: [] for candidate in candidates}
        for candidate in candidates:
            for other in candidates:
                if candidate.address == other.address:
                    continue
                if self._dominates(other, candidate):
                    dominated_by[candidate.address].append(other.address)

        decorated = tuple(
            StructuralAttractorCandidateV2(
                address=candidate.address,
                trajectory_ids=candidate.trajectory_ids,
                source_ids=candidate.source_ids,
                evidence=candidate.evidence,
                density=candidate.density,
                dominated_by=tuple(sorted(dominated_by[candidate.address])),
            )
            for candidate in candidates
        )
        pareto = tuple(
            sorted(
                candidate.address
                for candidate in decorated
                if not candidate.dominated_by
            )
        )

        if len(pareto) == 1:
            return StructuralAttractorResolutionV2(
                hierarchy,
                query,
                decorated,
                pareto,
                (),
                pareto[0],
                True,
                False,
                False,
                False,
                "unique-structural-attractor",
            )

        return StructuralAttractorResolutionV2(
            hierarchy,
            query,
            decorated,
            pareto,
            (),
            None,
            False,
            True,
            False,
            False,
            "crossed-or-equal-attractor-evidence",
        )
