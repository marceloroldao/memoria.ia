from __future__ import annotations

from dataclasses import dataclass

from .structural_attractor_v2 import (
    StructuralAssociationReader,
    StructuralAttractorResolutionV2,
    StructuralAttractorResolverV2,
)
from .structural_branch_state_v2 import StructuralBranchStateV2
from .structural_equivalence_v2 import (
    StructuralEquivalenceEngineV2,
    StructuralReformulationV2,
    structural_signature_v2,
)
from .structural_trajectory_v2 import StructuralTrajectoryIndex
from .temporal_state_v2 import (
    AddressStateReaderV2,
    TemporalPossibilityResolutionV2,
    TemporalStateOperationV2,
    TemporalStateResolutionV2,
    TemporalStateResolverV2,
    temporal_possibilities_from_branch_state,
)


@dataclass(frozen=True, slots=True)
class EquivalentAttractorAttemptV2:
    reformulation: StructuralReformulationV2
    attractor: StructuralAttractorResolutionV2


@dataclass(frozen=True, slots=True)
class ResolutiveInferenceDiagnosticsV2:
    direct_reason: str
    equivalent_attempts: int
    supported_equivalences: int
    external_calls: int = 0
    llm_calls: int = 0
    semantic_projection: bool = False


@dataclass(frozen=True, slots=True)
class ResolutiveInferenceResultV2:
    hierarchy_id: str
    query_addresses: tuple[int, ...]
    status: str
    source_tier: str
    resolved_address: int | None
    competing_addresses: tuple[int, ...]
    terminal: bool
    bounded_out: bool
    supporting_trajectory_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]
    equivalence_witness_ids: tuple[str, ...]
    conflicts: tuple[str, ...]
    direct_attractor: StructuralAttractorResolutionV2
    equivalent_attempts: tuple[EquivalentAttractorAttemptV2, ...]
    diagnostics: ResolutiveInferenceDiagnosticsV2


@dataclass(frozen=True, slots=True)
class ResolutiveTemporalStateResultV2:
    hierarchy_id: str
    state_address: int
    status: str
    supporting_trajectory_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]
    temporal: TemporalStateResolutionV2
    external_calls: int = 0
    llm_calls: int = 0
    semantic_projection: bool = False


@dataclass(frozen=True, slots=True)
class ResolutiveTemporalPossibilityResultV2:
    hierarchy_id: str
    status: str
    possibilities: TemporalPossibilityResolutionV2
    supporting_trajectory_ids: tuple[str, ...]
    external_calls: int = 0
    llm_calls: int = 0
    semantic_projection: bool = False


class ResolutiveInferenceEngineV2:
    """Read-only post-RC1 inference surface before language generation.

    Precedence is conservative:

    1. direct structural attractor evidence;
    2. directly witnessed structural-equivalence reformulations only when direct
       evidence is unresolved;
    3. unresolved.

    Direct ambiguity, terminal evidence and operational bounds are never erased by
    equivalence. Equivalent paths are still evaluated as diagnostics so conflicts
    remain visible, but they cannot override a direct resolved/ambiguous result.

    Temporal state is an explicit operation over the append-only evolving-address
    journal. Possible futures from R4 branch state are exposed separately and are
    never promoted into observed history.

    This layer performs no LLM/network calls and does not interpret natural language.
    """

    def __init__(
        self,
        trajectories: StructuralTrajectoryIndex,
        *,
        state_reader: AddressStateReaderV2 | None = None,
        association_field: StructuralAssociationReader | None = None,
        max_depth: int = 3,
    ) -> None:
        self.trajectories = trajectories
        self.attractor = StructuralAttractorResolverV2(
            trajectories,
            association_field=association_field,
            max_depth=max_depth,
        )
        self.equivalence = StructuralEquivalenceEngineV2(trajectories)
        self.temporal = (
            None
            if state_reader is None
            else TemporalStateResolverV2(state_reader)
        )

    @staticmethod
    def _collapse(addresses) -> tuple[int, ...]:
        output: list[int] = []
        current: int | None = None
        for raw in addresses:
            value = int(raw)
            if value < 0:
                raise ValueError("structural addresses must be >= 0")
            if value == current:
                continue
            output.append(value)
            current = value
        if not output:
            raise ValueError("query must contain at least one structural address")
        return tuple(output)

    def _trajectory_maps(
        self,
        *,
        hierarchy_id: str,
    ) -> tuple[dict[str, object], dict[str, str]]:
        by_id: dict[str, object] = {}
        provenance: dict[str, str] = {}
        for trajectory in self.trajectories.snapshot():
            if trajectory.hierarchy_id != hierarchy_id:
                continue
            by_id[trajectory.trajectory_id] = trajectory
            if trajectory.observation_id:
                provenance[trajectory.trajectory_id] = trajectory.observation_id
        return by_id, provenance

    @staticmethod
    def _candidate_trajectory_ids(
        resolution: StructuralAttractorResolutionV2,
        *,
        addresses: set[int] | None = None,
    ) -> set[str]:
        selected: set[str] = set(resolution.terminal_trajectory_ids)
        for candidate in resolution.candidates:
            if addresses is None or candidate.address in addresses:
                selected.update(candidate.trajectory_ids)
        return selected

    def _equivalence_witness_ids(
        self,
        query: tuple[int, ...],
        reformulations: tuple[StructuralReformulationV2, ...],
        *,
        hierarchy_id: str,
    ) -> tuple[str, ...]:
        query_id = structural_signature_v2(query, hierarchy_id=hierarchy_id)
        snapshot = self.equivalence.snapshot(hierarchy_id=hierarchy_id)
        witness_ids: set[str] = set()
        for reformulation in reformulations:
            if reformulation.direct:
                continue
            candidate = snapshot.candidate_by_pair(
                query_id,
                reformulation.signature_id,
            )
            if candidate is not None and candidate.state == "supported":
                witness_ids.update(candidate.supporting_witness_ids)
        return tuple(sorted(witness_ids))

    @staticmethod
    def _direct_competing_addresses(
        direct: StructuralAttractorResolutionV2,
    ) -> tuple[int, ...]:
        if direct.pareto_frontier:
            return tuple(sorted(set(direct.pareto_frontier)))
        return tuple(sorted({candidate.address for candidate in direct.candidates}))

    def infer_structural(
        self,
        addresses,
        *,
        hierarchy_id: str,
        candidate_limit: int = 64,
        branch_limit: int = 16,
    ) -> ResolutiveInferenceResultV2:
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        query = self._collapse(addresses)

        direct = self.attractor.resolve_addresses(
            query,
            hierarchy_id=hierarchy,
            candidate_limit=candidate_limit,
            branch_limit=branch_limit,
        )

        reformulations = self.equivalence.reformulate_addresses(
            query,
            hierarchy_id=hierarchy,
        )
        alternates = tuple(item for item in reformulations if not item.direct)
        attempts = tuple(
            EquivalentAttractorAttemptV2(
                reformulation=item,
                attractor=self.attractor.resolve_addresses(
                    item.addresses,
                    hierarchy_id=hierarchy,
                    candidate_limit=candidate_limit,
                    branch_limit=branch_limit,
                ),
            )
            for item in alternates
        )

        equivalence_witness_ids = self._equivalence_witness_ids(
            query,
            reformulations,
            hierarchy_id=hierarchy,
        )
        _, provenance_by_trajectory = self._trajectory_maps(
            hierarchy_id=hierarchy,
        )

        conflicts: set[str] = set()
        alt_addresses: set[int] = set()
        alt_terminal = False
        alt_ambiguous = False
        alt_bounded = False
        alt_support: set[str] = set()

        for attempt in attempts:
            result = attempt.attractor
            if result.bounded_out:
                alt_bounded = True
                conflicts.add("equivalent-path-bounded-out")
            if result.ambiguous:
                alt_ambiguous = True
                conflicts.add("equivalent-path-ambiguous")
            if result.terminal:
                alt_terminal = True
                alt_support.update(result.terminal_trajectory_ids)
            if result.resolved and result.resolved_address is not None:
                alt_addresses.add(result.resolved_address)
                alt_support.update(
                    self._candidate_trajectory_ids(
                        result,
                        addresses={result.resolved_address},
                    )
                )

        status: str
        source_tier: str
        resolved_address: int | None = None
        competing_addresses: tuple[int, ...] = ()
        terminal = False
        bounded_out = direct.bounded_out
        support: set[str] = set()

        if direct.bounded_out:
            status = "ambiguous"
            source_tier = "direct-attractor"
            competing_addresses = self._direct_competing_addresses(direct)
            support.update(self._candidate_trajectory_ids(direct))
            conflicts.add("direct-bounded-out")
        elif direct.resolved and direct.resolved_address is not None:
            status = "resolved"
            source_tier = "direct-attractor"
            resolved_address = direct.resolved_address
            support.update(
                self._candidate_trajectory_ids(
                    direct,
                    addresses={resolved_address},
                )
            )
            if alt_addresses and alt_addresses != {resolved_address}:
                conflicts.add("equivalent-path-disagrees-with-direct")
            if alt_terminal:
                conflicts.add("equivalent-terminal-competes-with-direct")
            if alt_ambiguous or alt_bounded:
                conflicts.add("equivalent-path-does-not-converge")
        elif direct.ambiguous:
            status = "ambiguous"
            source_tier = "direct-attractor"
            competing_addresses = self._direct_competing_addresses(direct)
            support.update(self._candidate_trajectory_ids(direct))
            conflicts.add("direct-structural-ambiguity")
        elif direct.terminal:
            status = "terminal"
            source_tier = "direct-attractor"
            terminal = True
            support.update(direct.terminal_trajectory_ids)
            if alt_addresses:
                conflicts.add("equivalent-forward-path-competes-with-direct-terminal")
        else:
            # Equivalent paths are fallback evidence only after direct evidence is
            # truly unresolved. They must agree and remain unbounded/unambiguous.
            if alt_bounded or alt_ambiguous:
                status = "ambiguous"
                source_tier = "equivalent-attractor"
                competing_addresses = tuple(sorted(alt_addresses))
                bounded_out = alt_bounded
                support.update(alt_support)
            elif alt_terminal and alt_addresses:
                status = "ambiguous"
                source_tier = "equivalent-attractor"
                competing_addresses = tuple(sorted(alt_addresses))
                support.update(alt_support)
                conflicts.add("equivalent-terminal-and-forward-outcomes")
            elif len(alt_addresses) == 1 and not alt_terminal:
                status = "resolved"
                source_tier = "equivalent-attractor"
                resolved_address = next(iter(alt_addresses))
                support.update(alt_support)
            elif len(alt_addresses) > 1:
                status = "ambiguous"
                source_tier = "equivalent-attractor"
                competing_addresses = tuple(sorted(alt_addresses))
                support.update(alt_support)
                conflicts.add("equivalent-paths-disagree")
            elif alt_terminal:
                status = "terminal"
                source_tier = "equivalent-attractor"
                terminal = True
                support.update(alt_support)
            else:
                status = "unresolved"
                source_tier = "none"

        provenance_ids = tuple(
            sorted(
                {
                    provenance_by_trajectory[trajectory_id]
                    for trajectory_id in support
                    if trajectory_id in provenance_by_trajectory
                }
            )
        )

        return ResolutiveInferenceResultV2(
            hierarchy_id=hierarchy,
            query_addresses=query,
            status=status,
            source_tier=source_tier,
            resolved_address=resolved_address,
            competing_addresses=competing_addresses,
            terminal=terminal,
            bounded_out=bounded_out,
            supporting_trajectory_ids=tuple(sorted(support)),
            provenance_ids=provenance_ids,
            equivalence_witness_ids=equivalence_witness_ids,
            conflicts=tuple(sorted(conflicts)),
            direct_attractor=direct,
            equivalent_attempts=attempts,
            diagnostics=ResolutiveInferenceDiagnosticsV2(
                direct_reason=direct.reason,
                equivalent_attempts=len(attempts),
                supported_equivalences=len(alternates),
            ),
        )

    def infer_temporal_state(
        self,
        state_address: int,
        *,
        hierarchy_id: str,
        operation: TemporalStateOperationV2 | str,
        anchor_revision_id: str | None = None,
    ) -> ResolutiveTemporalStateResultV2:
        if self.temporal is None:
            raise RuntimeError("state_reader is required for temporal state inference")
        result = self.temporal.resolve(
            state_address,
            hierarchy_id=hierarchy_id,
            operation=operation,
            anchor_revision_id=anchor_revision_id,
        )
        trajectory_ids = tuple(
            sorted(
                {
                    trajectory_id
                    for revision in result.revisions
                    for trajectory_id in revision.trajectory_ids
                }
            )
        )
        provenance_ids = tuple(
            sorted(
                {
                    provenance_id
                    for revision in result.revisions
                    for provenance_id in revision.provenance_ids
                }
            )
        )
        status = (
            "ambiguous"
            if result.ambiguous
            else "resolved"
            if result.resolved
            else "unresolved"
        )
        return ResolutiveTemporalStateResultV2(
            hierarchy_id=result.hierarchy_id,
            state_address=result.address,
            status=status,
            supporting_trajectory_ids=trajectory_ids,
            provenance_ids=provenance_ids,
            temporal=result,
        )

    @staticmethod
    def infer_temporal_possibilities(
        state: StructuralBranchStateV2,
    ) -> ResolutiveTemporalPossibilityResultV2:
        result = temporal_possibilities_from_branch_state(state)
        trajectory_ids = tuple(
            sorted(
                {
                    trajectory_id
                    for outcome in result.outcomes
                    for trajectory_id in outcome.trajectory_ids
                }
            )
        )
        status = (
            "ambiguous"
            if result.ambiguous
            else "resolved"
            if result.resolved
            else "unresolved"
        )
        return ResolutiveTemporalPossibilityResultV2(
            hierarchy_id=result.hierarchy_id,
            status=status,
            possibilities=result,
            supporting_trajectory_ids=trajectory_ids,
        )
