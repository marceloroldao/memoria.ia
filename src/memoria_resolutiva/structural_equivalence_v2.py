from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from itertools import combinations
import json
from typing import Callable

from .structural_trajectory_v2 import StructuralTrajectory, StructuralTrajectoryIndex


def _digest(kind: str, payload: object) -> str:
    encoded = json.dumps(
        {"kind": kind, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "se6:" + blake2b(encoded, digest_size=20).hexdigest()


def structural_signature_v2(
    addresses: tuple[int, ...],
    *,
    hierarchy_id: str,
) -> str:
    hierarchy = str(hierarchy_id).strip()
    if not hierarchy:
        raise ValueError("hierarchy_id must be non-empty")
    if not addresses:
        raise ValueError("structural signature requires at least one address")
    values = tuple(int(value) for value in addresses)
    if any(value < 0 for value in values):
        raise ValueError("structural addresses must be >= 0")
    return _digest(
        "signature",
        {
            "hierarchy_id": hierarchy,
            "addresses": list(values),
        },
    )


@dataclass(frozen=True, slots=True)
class StructuralSignatureV2:
    signature_id: str
    hierarchy_id: str
    addresses: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class StructuralConvergenceWitnessV2:
    witness_id: str
    hierarchy_id: str
    left_signature_id: str
    right_signature_id: str
    bridge_addresses: tuple[int, ...]
    left_terminal_address: int
    right_terminal_address: int
    left_trajectory_id: str
    right_trajectory_id: str
    left_lineage_id: str
    right_lineage_id: str

    @property
    def supports_equivalence(self) -> bool:
        return self.left_terminal_address == self.right_terminal_address

    @property
    def lineage_pair(self) -> tuple[str, str]:
        return (self.left_lineage_id, self.right_lineage_id)


@dataclass(frozen=True, slots=True)
class StructuralEquivalenceCandidateV2:
    hierarchy_id: str
    left_signature_id: str
    right_signature_id: str
    shared_terminal_addresses: tuple[int, ...]
    supporting_witness_ids: tuple[str, ...]
    contradicting_witness_ids: tuple[str, ...]
    supporting_lineage_pairs: tuple[tuple[str, str], ...]
    contradicting_lineage_pairs: tuple[tuple[str, str], ...]
    state: str

    @property
    def independent_convergence(self) -> int:
        return len(self.supporting_lineage_pairs)

    @property
    def independent_divergence(self) -> int:
        return len(self.contradicting_lineage_pairs)


@dataclass(frozen=True, slots=True)
class StructuralReformulationV2:
    signature_id: str
    addresses: tuple[int, ...]
    direct: bool
    equivalence_state: str
    independent_convergence: int
    independent_divergence: int


@dataclass(frozen=True, slots=True)
class StructuralEquivalenceSnapshotV2:
    hierarchy_id: str
    signatures: tuple[StructuralSignatureV2, ...]
    witnesses: tuple[StructuralConvergenceWitnessV2, ...]
    candidates: tuple[StructuralEquivalenceCandidateV2, ...]
    skipped_hyperdense_bridges: tuple[tuple[int, ...], ...]
    semantic_projection: bool = False

    def signature_by_id(self) -> dict[str, StructuralSignatureV2]:
        return {item.signature_id: item for item in self.signatures}

    def candidate_by_pair(
        self,
        left_signature_id: str,
        right_signature_id: str,
    ) -> StructuralEquivalenceCandidateV2 | None:
        left, right = sorted((str(left_signature_id), str(right_signature_id)))
        for candidate in self.candidates:
            if (
                candidate.left_signature_id == left
                and candidate.right_signature_id == right
            ):
                return candidate
        return None


@dataclass(frozen=True, slots=True)
class _OccurrenceView:
    signature: StructuralSignatureV2
    bridge_addresses: tuple[int, ...]
    terminal_address: int
    trajectory_id: str
    lineage_id: str


class StructuralEquivalenceEngineV2:
    """Derive direct, revocable structural equivalence from independent convergence.

    The engine does not infer meaning from address labels and does not use embeddings,
    probabilities or learned scalar weights. A source signature can become a direct
    equivalence candidate only when independent trajectory lineages repeatedly enter
    the same local bridge and converge to the same terminal region.

    Divergent terminals through the same bridge are explicit contradiction evidence.
    Equivalence is never made transitive here: A~B and B~C do not manufacture A~C.
    Query reformulation is read-only and returns direct supported alternatives only.
    """

    def __init__(
        self,
        trajectories: StructuralTrajectoryIndex,
        *,
        min_bridge_addresses: int = 2,
        min_supporting_lineages: int = 2,
        max_bucket_signatures: int = 32,
        max_occurrences_per_signature: int = 16,
        max_witnesses_per_pair: int = 64,
        lineage_resolver: Callable[[StructuralTrajectory], str] | None = None,
    ) -> None:
        if min_bridge_addresses < 1:
            raise ValueError("min_bridge_addresses must be >= 1")
        if min_supporting_lineages < 2:
            raise ValueError("min_supporting_lineages must be >= 2")
        if max_bucket_signatures < 2:
            raise ValueError("max_bucket_signatures must be >= 2")
        if max_occurrences_per_signature < 1:
            raise ValueError("max_occurrences_per_signature must be >= 1")
        if max_witnesses_per_pair < 1:
            raise ValueError("max_witnesses_per_pair must be >= 1")
        self.trajectories = trajectories
        self.min_bridge_addresses = int(min_bridge_addresses)
        self.min_supporting_lineages = int(min_supporting_lineages)
        self.max_bucket_signatures = int(max_bucket_signatures)
        self.max_occurrences_per_signature = int(max_occurrences_per_signature)
        self.max_witnesses_per_pair = int(max_witnesses_per_pair)
        self.lineage_resolver = lineage_resolver or self._default_lineage

    @staticmethod
    def _default_lineage(trajectory: StructuralTrajectory) -> str:
        value = str(trajectory.source_id).strip()
        if not value:
            raise ValueError("trajectory source_id must be non-empty")
        return value

    def _occurrence_views(
        self,
        *,
        hierarchy_id: str,
    ) -> tuple[_OccurrenceView, ...]:
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        width = self.min_bridge_addresses
        rows: list[_OccurrenceView] = []

        for trajectory in self.trajectories.snapshot():
            if trajectory.hierarchy_id != hierarchy:
                continue
            addresses = trajectory.addresses
            if len(addresses) < width + 2:
                continue
            prefix = tuple(addresses[: -(width + 1)])
            if not prefix:
                continue
            bridge = tuple(addresses[-(width + 1) : -1])
            terminal = int(addresses[-1])
            signature = StructuralSignatureV2(
                signature_id=structural_signature_v2(
                    prefix,
                    hierarchy_id=hierarchy,
                ),
                hierarchy_id=hierarchy,
                addresses=prefix,
            )
            lineage = str(self.lineage_resolver(trajectory)).strip()
            if not lineage:
                raise ValueError("lineage_resolver must return a non-empty id")
            rows.append(
                _OccurrenceView(
                    signature=signature,
                    bridge_addresses=bridge,
                    terminal_address=terminal,
                    trajectory_id=trajectory.trajectory_id,
                    lineage_id=lineage,
                )
            )

        rows.sort(
            key=lambda item: (
                item.bridge_addresses,
                item.signature.signature_id,
                item.lineage_id,
                item.trajectory_id,
                item.terminal_address,
            )
        )
        return tuple(rows)

    @staticmethod
    def _witness(
        left: _OccurrenceView,
        right: _OccurrenceView,
    ) -> StructuralConvergenceWitnessV2:
        left_sig, right_sig = sorted(
            (left.signature.signature_id, right.signature.signature_id)
        )
        if left.signature.signature_id == left_sig:
            l, r = left, right
        else:
            l, r = right, left
        witness_id = _digest(
            "witness",
            {
                "hierarchy_id": l.signature.hierarchy_id,
                "bridge_addresses": list(l.bridge_addresses),
                "left_signature_id": left_sig,
                "right_signature_id": right_sig,
                "left_trajectory_id": l.trajectory_id,
                "right_trajectory_id": r.trajectory_id,
                "left_terminal_address": l.terminal_address,
                "right_terminal_address": r.terminal_address,
            },
        )
        return StructuralConvergenceWitnessV2(
            witness_id=witness_id,
            hierarchy_id=l.signature.hierarchy_id,
            left_signature_id=left_sig,
            right_signature_id=right_sig,
            bridge_addresses=l.bridge_addresses,
            left_terminal_address=l.terminal_address,
            right_terminal_address=r.terminal_address,
            left_trajectory_id=l.trajectory_id,
            right_trajectory_id=r.trajectory_id,
            left_lineage_id=l.lineage_id,
            right_lineage_id=r.lineage_id,
        )

    def _evaluate_pair(
        self,
        witnesses: tuple[StructuralConvergenceWitnessV2, ...],
        *,
        hierarchy_id: str,
        left_signature_id: str,
        right_signature_id: str,
    ) -> StructuralEquivalenceCandidateV2:
        support_witnesses = tuple(
            sorted(w.witness_id for w in witnesses if w.supports_equivalence)
        )
        contradiction_witnesses = tuple(
            sorted(w.witness_id for w in witnesses if not w.supports_equivalence)
        )
        support_pairs = tuple(
            sorted({w.lineage_pair for w in witnesses if w.supports_equivalence})
        )
        contradiction_pairs = tuple(
            sorted({w.lineage_pair for w in witnesses if not w.supports_equivalence})
        )
        shared_terminals = tuple(
            sorted(
                {
                    w.left_terminal_address
                    for w in witnesses
                    if w.supports_equivalence
                }
            )
        )

        support_count = len(support_pairs)
        contradiction_count = len(contradiction_pairs)
        if (
            support_count >= self.min_supporting_lineages
            and support_count > contradiction_count
        ):
            state = "supported"
        elif contradiction_count > 0 and contradiction_count >= support_count:
            state = "contradicted"
        elif support_count > 0:
            state = "candidate"
        else:
            state = "insufficient"

        return StructuralEquivalenceCandidateV2(
            hierarchy_id=hierarchy_id,
            left_signature_id=left_signature_id,
            right_signature_id=right_signature_id,
            shared_terminal_addresses=shared_terminals,
            supporting_witness_ids=support_witnesses,
            contradicting_witness_ids=contradiction_witnesses,
            supporting_lineage_pairs=support_pairs,
            contradicting_lineage_pairs=contradiction_pairs,
            state=state,
        )

    def snapshot(
        self,
        *,
        hierarchy_id: str,
    ) -> StructuralEquivalenceSnapshotV2:
        hierarchy = str(hierarchy_id).strip()
        occurrences = self._occurrence_views(hierarchy_id=hierarchy)
        signatures = {
            item.signature.signature_id: item.signature
            for item in occurrences
        }

        buckets: dict[
            tuple[int, ...],
            dict[str, list[_OccurrenceView]],
        ] = {}
        for occurrence in occurrences:
            by_signature = buckets.setdefault(occurrence.bridge_addresses, {})
            by_signature.setdefault(
                occurrence.signature.signature_id,
                [],
            ).append(occurrence)

        witnesses: list[StructuralConvergenceWitnessV2] = []
        skipped: list[tuple[int, ...]] = []

        for bridge, by_signature in sorted(buckets.items()):
            signature_ids = tuple(sorted(by_signature))
            if len(signature_ids) < 2:
                continue
            if len(signature_ids) > self.max_bucket_signatures:
                skipped.append(bridge)
                continue

            for left_sig, right_sig in combinations(signature_ids, 2):
                left_rows = tuple(
                    sorted(
                        by_signature[left_sig],
                        key=lambda item: (
                            item.lineage_id,
                            item.trajectory_id,
                            item.terminal_address,
                        ),
                    )[: self.max_occurrences_per_signature]
                )
                right_rows = tuple(
                    sorted(
                        by_signature[right_sig],
                        key=lambda item: (
                            item.lineage_id,
                            item.trajectory_id,
                            item.terminal_address,
                        ),
                    )[: self.max_occurrences_per_signature]
                )

                pair_witnesses: list[StructuralConvergenceWitnessV2] = []
                for left in left_rows:
                    for right in right_rows:
                        if left.lineage_id == right.lineage_id:
                            continue
                        pair_witnesses.append(self._witness(left, right))

                pair_witnesses.sort(key=lambda item: item.witness_id)
                witnesses.extend(pair_witnesses[: self.max_witnesses_per_pair])

        unique_witnesses = {
            witness.witness_id: witness
            for witness in witnesses
        }
        ordered_witnesses = tuple(
            unique_witnesses[key]
            for key in sorted(unique_witnesses)
        )

        by_pair: dict[
            tuple[str, str],
            list[StructuralConvergenceWitnessV2],
        ] = {}
        for witness in ordered_witnesses:
            key = (
                witness.left_signature_id,
                witness.right_signature_id,
            )
            by_pair.setdefault(key, []).append(witness)

        candidates = tuple(
            self._evaluate_pair(
                tuple(rows),
                hierarchy_id=hierarchy,
                left_signature_id=left,
                right_signature_id=right,
            )
            for (left, right), rows in sorted(by_pair.items())
        )

        return StructuralEquivalenceSnapshotV2(
            hierarchy_id=hierarchy,
            signatures=tuple(
                signatures[key]
                for key in sorted(signatures)
            ),
            witnesses=ordered_witnesses,
            candidates=candidates,
            skipped_hyperdense_bridges=tuple(sorted(set(skipped))),
        )

    def evaluate(
        self,
        left_addresses,
        right_addresses,
        *,
        hierarchy_id: str,
    ) -> StructuralEquivalenceCandidateV2:
        hierarchy = str(hierarchy_id).strip()
        left_tuple = tuple(int(value) for value in left_addresses)
        right_tuple = tuple(int(value) for value in right_addresses)
        left_id = structural_signature_v2(left_tuple, hierarchy_id=hierarchy)
        right_id = structural_signature_v2(right_tuple, hierarchy_id=hierarchy)
        left_id, right_id = sorted((left_id, right_id))
        snapshot = self.snapshot(hierarchy_id=hierarchy)
        candidate = snapshot.candidate_by_pair(left_id, right_id)
        if candidate is not None:
            return candidate
        return StructuralEquivalenceCandidateV2(
            hierarchy_id=hierarchy,
            left_signature_id=left_id,
            right_signature_id=right_id,
            shared_terminal_addresses=(),
            supporting_witness_ids=(),
            contradicting_witness_ids=(),
            supporting_lineage_pairs=(),
            contradicting_lineage_pairs=(),
            state="insufficient",
        )

    def reformulate_addresses(
        self,
        addresses,
        *,
        hierarchy_id: str,
    ) -> tuple[StructuralReformulationV2, ...]:
        hierarchy = str(hierarchy_id).strip()
        query = tuple(int(value) for value in addresses)
        query_id = structural_signature_v2(query, hierarchy_id=hierarchy)
        snapshot = self.snapshot(hierarchy_id=hierarchy)
        signatures = snapshot.signature_by_id()

        output: list[StructuralReformulationV2] = [
            StructuralReformulationV2(
                signature_id=query_id,
                addresses=query,
                direct=True,
                equivalence_state="direct",
                independent_convergence=0,
                independent_divergence=0,
            )
        ]

        for candidate in snapshot.candidates:
            if candidate.state != "supported":
                continue
            if candidate.left_signature_id == query_id:
                other = candidate.right_signature_id
            elif candidate.right_signature_id == query_id:
                other = candidate.left_signature_id
            else:
                continue
            signature = signatures.get(other)
            if signature is None:
                continue
            output.append(
                StructuralReformulationV2(
                    signature_id=other,
                    addresses=signature.addresses,
                    direct=False,
                    equivalence_state=candidate.state,
                    independent_convergence=candidate.independent_convergence,
                    independent_divergence=candidate.independent_divergence,
                )
            )

        output.sort(
            key=lambda item: (
                not item.direct,
                item.signature_id,
            )
        )
        return tuple(output)
