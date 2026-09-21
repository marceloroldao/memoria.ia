from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable


_VALID_ORIENTATIONS = frozenset({"a_before_b", "simultaneous", "b_before_a"})


def _stable_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = str(raw)
        if not value:
            raise ValueError("provenance values must be non-empty")
        if value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)


def _canonical_pair(
    pattern_a: str,
    pattern_b: str,
    orientation: str,
) -> tuple[str, str, str]:
    a = str(pattern_a)
    b = str(pattern_b)
    if not a or not b:
        raise ValueError("pattern addresses must be non-empty")
    if a == b:
        raise ValueError("temporal observation requires two distinct patterns")
    if orientation not in _VALID_ORIENTATIONS:
        raise ValueError("unsupported temporal orientation")

    if a < b:
        return a, b, orientation
    flipped = {
        "a_before_b": "b_before_a",
        "b_before_a": "a_before_b",
        "simultaneous": "simultaneous",
    }[orientation]
    return b, a, flipped


@dataclass(frozen=True, slots=True)
class StructuralTemporalObservation:
    """One admitted presemantic temporal observation snapshot.

    The record preserves opaque pattern addresses, temporal orientation, upstream
    evidence metrics and provenance.  It does not assert causality, truth, semantic
    meaning, or a world law.
    """

    observation_id: str
    pattern_a: str
    pattern_b: str
    orientation: str
    source_candidate_id: str
    rho: float
    selectivity: float
    temporal_stability: float
    evidence_score: float
    orientation_confidence: float
    mean_dt: float
    variance_dt: float
    supporting_slice_ids: tuple[str, ...]
    supporting_frame_ids: tuple[str, ...]
    provenance: str = ""


@dataclass(frozen=True, slots=True)
class StructuralTemporalHypothesis:
    pattern_a: str
    pattern_b: str
    orientation: str
    supporting_observation_ids: tuple[str, ...]
    supporting_slice_ids: tuple[str, ...]
    supporting_frame_ids: tuple[str, ...]
    source_candidate_ids: tuple[str, ...]
    independent_support: int
    supported: bool


@dataclass(frozen=True, slots=True)
class StructuralTemporalResolution:
    pattern_a: str
    pattern_b: str
    hypotheses: tuple[StructuralTemporalHypothesis, ...]
    supported_orientation: str | None
    resolved: bool
    ambiguous: bool
    reason: str


class StructuralTemporalObservationMemory:
    """Additive memory for passive temporal structure, separate from causal episodes.

    Reinforcement is derived only from unique supporting RealitySlice provenance.
    Replaying the same evidence bundle is idempotent. Competing orientations remain
    visible and can independently accumulate support; no orientation is deleted or
    marked false when another gains support.
    """

    def __init__(self) -> None:
        self._observations: list[StructuralTemporalObservation] = []
        self._fingerprints: dict[str, StructuralTemporalObservation] = {}
        self._next_id = 1

    @staticmethod
    def _fingerprint(
        *,
        pattern_a: str,
        pattern_b: str,
        orientation: str,
        source_candidate_id: str,
        supporting_slice_ids: tuple[str, ...],
        supporting_frame_ids: tuple[str, ...],
    ) -> str:
        raw = "|".join(
            (
                pattern_a,
                pattern_b,
                orientation,
                source_candidate_id,
                ",".join(supporting_slice_ids),
                ",".join(supporting_frame_ids),
            )
        )
        return sha256(raw.encode("utf-8")).hexdigest()

    def ingest_observation(
        self,
        *,
        pattern_a: str,
        pattern_b: str,
        orientation: str,
        source_candidate_id: str,
        rho: float,
        selectivity: float,
        temporal_stability: float,
        evidence_score: float,
        orientation_confidence: float,
        mean_dt: float,
        variance_dt: float,
        supporting_slice_ids: Iterable[str],
        supporting_frame_ids: Iterable[str] = (),
        provenance: str = "",
    ) -> StructuralTemporalObservation:
        if not source_candidate_id:
            raise ValueError("source_candidate_id must be non-empty")
        a, b, canonical_orientation = _canonical_pair(
            pattern_a,
            pattern_b,
            orientation,
        )
        slices = tuple(sorted(_stable_unique(supporting_slice_ids)))
        frames = tuple(sorted(_stable_unique(supporting_frame_ids)))
        if not slices:
            raise ValueError("supporting_slice_ids must be non-empty")

        metrics = {
            "rho": float(rho),
            "selectivity": float(selectivity),
            "temporal_stability": float(temporal_stability),
            "evidence_score": float(evidence_score),
            "orientation_confidence": float(orientation_confidence),
            "variance_dt": float(variance_dt),
        }
        if any(value < 0 for value in metrics.values()):
            raise ValueError("temporal evidence metrics must be non-negative")
        if metrics["rho"] > 1 or metrics["temporal_stability"] > 1 or metrics["orientation_confidence"] > 1:
            raise ValueError("probability-like evidence metrics must be <= 1")

        fingerprint = self._fingerprint(
            pattern_a=a,
            pattern_b=b,
            orientation=canonical_orientation,
            source_candidate_id=source_candidate_id,
            supporting_slice_ids=slices,
            supporting_frame_ids=frames,
        )
        existing = self._fingerprints.get(fingerprint)
        if existing is not None:
            return existing

        observation = StructuralTemporalObservation(
            observation_id=f"STO{self._next_id}",
            pattern_a=a,
            pattern_b=b,
            orientation=canonical_orientation,
            source_candidate_id=source_candidate_id,
            rho=metrics["rho"],
            selectivity=metrics["selectivity"],
            temporal_stability=metrics["temporal_stability"],
            evidence_score=metrics["evidence_score"],
            orientation_confidence=metrics["orientation_confidence"],
            mean_dt=float(mean_dt),
            variance_dt=metrics["variance_dt"],
            supporting_slice_ids=slices,
            supporting_frame_ids=frames,
            provenance=str(provenance),
        )
        self._next_id += 1
        self._observations.append(observation)
        self._fingerprints[fingerprint] = observation
        return observation

    def snapshot(self) -> tuple[StructuralTemporalObservation, ...]:
        return tuple(self._observations)

    @classmethod
    def restore(
        cls,
        observations: tuple[StructuralTemporalObservation, ...],
    ) -> "StructuralTemporalObservationMemory":
        memory = cls()
        for item in observations:
            restored = memory.ingest_observation(
                pattern_a=item.pattern_a,
                pattern_b=item.pattern_b,
                orientation=item.orientation,
                source_candidate_id=item.source_candidate_id,
                rho=item.rho,
                selectivity=item.selectivity,
                temporal_stability=item.temporal_stability,
                evidence_score=item.evidence_score,
                orientation_confidence=item.orientation_confidence,
                mean_dt=item.mean_dt,
                variance_dt=item.variance_dt,
                supporting_slice_ids=item.supporting_slice_ids,
                supporting_frame_ids=item.supporting_frame_ids,
                provenance=item.provenance,
            )
            # Preserve durable observation IDs from the snapshot.
            if restored.observation_id != item.observation_id:
                raise ValueError("structural temporal observation snapshot order is invalid")
        return memory

    def resolve(
        self,
        pattern_a: str,
        pattern_b: str,
        *,
        min_independent_slices: int = 3,
    ) -> StructuralTemporalResolution:
        if min_independent_slices < 1:
            raise ValueError("min_independent_slices must be >= 1")

        a, b, _ = _canonical_pair(pattern_a, pattern_b, "simultaneous")
        grouped: dict[str, list[StructuralTemporalObservation]] = {
            orientation: [] for orientation in sorted(_VALID_ORIENTATIONS)
        }
        for observation in self._observations:
            if observation.pattern_a == a and observation.pattern_b == b:
                grouped[observation.orientation].append(observation)

        hypotheses: list[StructuralTemporalHypothesis] = []
        for orientation in sorted(_VALID_ORIENTATIONS):
            observations = grouped[orientation]
            if not observations:
                continue
            slice_ids = tuple(
                sorted(
                    {
                        slice_id
                        for observation in observations
                        for slice_id in observation.supporting_slice_ids
                    }
                )
            )
            frame_ids = tuple(
                sorted(
                    {
                        frame_id
                        for observation in observations
                        for frame_id in observation.supporting_frame_ids
                    }
                )
            )
            observation_ids = tuple(
                sorted(observation.observation_id for observation in observations)
            )
            candidate_ids = tuple(
                sorted({observation.source_candidate_id for observation in observations})
            )
            independent_support = len(slice_ids)
            hypotheses.append(
                StructuralTemporalHypothesis(
                    pattern_a=a,
                    pattern_b=b,
                    orientation=orientation,
                    supporting_observation_ids=observation_ids,
                    supporting_slice_ids=slice_ids,
                    supporting_frame_ids=frame_ids,
                    source_candidate_ids=candidate_ids,
                    independent_support=independent_support,
                    supported=independent_support >= min_independent_slices,
                )
            )

        hypotheses.sort(key=lambda item: item.orientation)
        supported = tuple(item for item in hypotheses if item.supported)
        if not supported:
            return StructuralTemporalResolution(
                pattern_a=a,
                pattern_b=b,
                hypotheses=tuple(hypotheses),
                supported_orientation=None,
                resolved=False,
                ambiguous=False,
                reason="insufficient-supported-orientation",
            )
        if len(supported) > 1:
            return StructuralTemporalResolution(
                pattern_a=a,
                pattern_b=b,
                hypotheses=tuple(hypotheses),
                supported_orientation=None,
                resolved=False,
                ambiguous=True,
                reason="competing-supported-orientations",
            )

        return StructuralTemporalResolution(
            pattern_a=a,
            pattern_b=b,
            hypotheses=tuple(hypotheses),
            supported_orientation=supported[0].orientation,
            resolved=True,
            ambiguous=False,
            reason="single-supported-orientation",
        )
