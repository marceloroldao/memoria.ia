from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable


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


def _canonical_context(
    antecedent_patterns: Iterable[str],
    consequence_pattern: str,
) -> tuple[tuple[str, str], str]:
    values = tuple(str(value) for value in antecedent_patterns)
    if len(values) != 2:
        raise ValueError("structural context requires exactly two antecedent patterns")
    if any(not value for value in values):
        raise ValueError("antecedent pattern addresses must be non-empty")
    if values[0] == values[1]:
        raise ValueError("structural context antecedents must be distinct")
    consequence = str(consequence_pattern)
    if not consequence:
        raise ValueError("consequence pattern address must be non-empty")
    if consequence in values:
        raise ValueError("consequence must differ from context antecedents")
    return tuple(sorted(values)), consequence


@dataclass(frozen=True, slots=True)
class StructuralContextObservation:
    """One admitted presemantic higher-order structural observation."""

    observation_id: str
    antecedent_patterns: tuple[str, str]
    consequence_pattern: str
    source_candidate_id: str
    rho: float
    context_coverage: float
    temporal_stability: float
    context_reliability: float
    lower_order_reliabilities: tuple[float, float]
    repetitions: int
    mean_delay: float
    variance_delay: float
    supporting_slice_ids: tuple[str, ...]
    supporting_frame_ids: tuple[str, ...]
    provenance: str = ""


@dataclass(frozen=True, slots=True)
class StructuralContextHypothesis:
    antecedent_patterns: tuple[str, str]
    consequence_pattern: str
    supporting_observation_ids: tuple[str, ...]
    supporting_slice_ids: tuple[str, ...]
    supporting_frame_ids: tuple[str, ...]
    source_candidate_ids: tuple[str, ...]
    independent_support: int
    supported: bool


class StructuralContextObservationMemory:
    """Additive memory for sparse higher-order presemantic structure.

    The antecedent context remains a two-address tuple. No synthetic context pattern is
    created. Multiple consequences for the same context remain visible and are not
    ranked away by evidence metrics.
    """

    def __init__(self) -> None:
        self._observations: list[StructuralContextObservation] = []
        self._fingerprints: dict[str, StructuralContextObservation] = {}
        self._next_id = 1

    @staticmethod
    def _fingerprint(
        *,
        antecedent_patterns: tuple[str, str],
        consequence_pattern: str,
        source_candidate_id: str,
        rho: float,
        context_coverage: float,
        temporal_stability: float,
        context_reliability: float,
        lower_order_reliabilities: tuple[float, float],
        repetitions: int,
        mean_delay: float,
        variance_delay: float,
        supporting_slice_ids: tuple[str, ...],
        supporting_frame_ids: tuple[str, ...],
        provenance: str,
    ) -> str:
        raw = "|".join(
            (
                ",".join(antecedent_patterns),
                consequence_pattern,
                source_candidate_id,
                repr(rho),
                repr(context_coverage),
                repr(temporal_stability),
                repr(context_reliability),
                ",".join(repr(value) for value in lower_order_reliabilities),
                str(repetitions),
                repr(mean_delay),
                repr(variance_delay),
                ",".join(supporting_slice_ids),
                ",".join(supporting_frame_ids),
                provenance,
            )
        )
        return sha256(raw.encode("utf-8")).hexdigest()

    def ingest_observation(
        self,
        *,
        antecedent_patterns: Iterable[str],
        consequence_pattern: str,
        source_candidate_id: str,
        rho: float,
        context_coverage: float,
        temporal_stability: float,
        context_reliability: float,
        lower_order_reliabilities: Iterable[float],
        repetitions: int,
        mean_delay: float,
        variance_delay: float,
        supporting_slice_ids: Iterable[str],
        supporting_frame_ids: Iterable[str] = (),
        provenance: str = "",
    ) -> StructuralContextObservation:
        if not source_candidate_id:
            raise ValueError("source_candidate_id must be non-empty")
        original_antecedents = tuple(str(value) for value in antecedent_patterns)
        antecedents, consequence = _canonical_context(
            original_antecedents,
            consequence_pattern,
        )
        slices = tuple(sorted(_stable_unique(supporting_slice_ids)))
        frames = tuple(sorted(_stable_unique(supporting_frame_ids)))
        if not slices:
            raise ValueError("supporting_slice_ids must be non-empty")

        lower = tuple(float(value) for value in lower_order_reliabilities)
        if len(lower) != 2:
            raise ValueError("lower_order_reliabilities must contain exactly two values")
        # Canonicalize lower-order metrics together with antecedents.
        if original_antecedents[0] > original_antecedents[1]:
            lower = (lower[1], lower[0])

        metrics = {
            "rho": float(rho),
            "context_coverage": float(context_coverage),
            "temporal_stability": float(temporal_stability),
            "context_reliability": float(context_reliability),
            "variance_delay": float(variance_delay),
        }
        if repetitions < 1:
            raise ValueError("repetitions must be >= 1")
        if any(value < 0 for value in metrics.values()) or any(
            value < 0 for value in lower
        ):
            raise ValueError("structural context evidence metrics must be non-negative")
        for name in (
            "rho",
            "context_coverage",
            "temporal_stability",
            "context_reliability",
        ):
            if metrics[name] > 1:
                raise ValueError(f"{name} must be <= 1")
        if any(value > 1 for value in lower):
            raise ValueError("lower_order_reliabilities must be <= 1")

        fingerprint = self._fingerprint(
            antecedent_patterns=antecedents,
            consequence_pattern=consequence,
            source_candidate_id=str(source_candidate_id),
            rho=metrics["rho"],
            context_coverage=metrics["context_coverage"],
            temporal_stability=metrics["temporal_stability"],
            context_reliability=metrics["context_reliability"],
            lower_order_reliabilities=lower,
            repetitions=int(repetitions),
            mean_delay=float(mean_delay),
            variance_delay=metrics["variance_delay"],
            supporting_slice_ids=slices,
            supporting_frame_ids=frames,
            provenance=str(provenance),
        )
        existing = self._fingerprints.get(fingerprint)
        if existing is not None:
            return existing

        observation = StructuralContextObservation(
            observation_id=f"SCO{self._next_id}",
            antecedent_patterns=antecedents,
            consequence_pattern=consequence,
            source_candidate_id=str(source_candidate_id),
            rho=metrics["rho"],
            context_coverage=metrics["context_coverage"],
            temporal_stability=metrics["temporal_stability"],
            context_reliability=metrics["context_reliability"],
            lower_order_reliabilities=lower,
            repetitions=int(repetitions),
            mean_delay=float(mean_delay),
            variance_delay=metrics["variance_delay"],
            supporting_slice_ids=slices,
            supporting_frame_ids=frames,
            provenance=str(provenance),
        )
        self._next_id += 1
        self._observations.append(observation)
        self._fingerprints[fingerprint] = observation
        return observation

    def snapshot(self) -> tuple[StructuralContextObservation, ...]:
        return tuple(self._observations)

    @classmethod
    def restore(
        cls,
        observations: tuple[StructuralContextObservation, ...],
    ) -> "StructuralContextObservationMemory":
        memory = cls()
        for item in observations:
            restored = memory.ingest_observation(
                antecedent_patterns=item.antecedent_patterns,
                consequence_pattern=item.consequence_pattern,
                source_candidate_id=item.source_candidate_id,
                rho=item.rho,
                context_coverage=item.context_coverage,
                temporal_stability=item.temporal_stability,
                context_reliability=item.context_reliability,
                lower_order_reliabilities=item.lower_order_reliabilities,
                repetitions=item.repetitions,
                mean_delay=item.mean_delay,
                variance_delay=item.variance_delay,
                supporting_slice_ids=item.supporting_slice_ids,
                supporting_frame_ids=item.supporting_frame_ids,
                provenance=item.provenance,
            )
            if restored.observation_id != item.observation_id:
                raise ValueError("structural context snapshot order is invalid")
        return memory

    def resolve(
        self,
        antecedent_patterns: Iterable[str],
        consequence_pattern: str,
        *,
        min_independent_slices: int = 3,
    ) -> StructuralContextHypothesis | None:
        if min_independent_slices < 1:
            raise ValueError("min_independent_slices must be >= 1")
        antecedents, consequence = _canonical_context(
            antecedent_patterns,
            consequence_pattern,
        )
        observations = [
            item
            for item in self._observations
            if item.antecedent_patterns == antecedents
            and item.consequence_pattern == consequence
        ]
        if not observations:
            return None

        slices = tuple(
            sorted(
                {
                    slice_id
                    for item in observations
                    for slice_id in item.supporting_slice_ids
                }
            )
        )
        frames = tuple(
            sorted(
                {
                    frame_id
                    for item in observations
                    for frame_id in item.supporting_frame_ids
                }
            )
        )
        observation_ids = tuple(
            sorted(item.observation_id for item in observations)
        )
        candidate_ids = tuple(
            sorted({item.source_candidate_id for item in observations})
        )
        support = len(slices)
        return StructuralContextHypothesis(
            antecedent_patterns=antecedents,
            consequence_pattern=consequence,
            supporting_observation_ids=observation_ids,
            supporting_slice_ids=slices,
            supporting_frame_ids=frames,
            source_candidate_ids=candidate_ids,
            independent_support=support,
            supported=support >= min_independent_slices,
        )
