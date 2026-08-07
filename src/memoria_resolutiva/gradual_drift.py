from __future__ import annotations

from dataclasses import dataclass

from .temporal_memory import TemporalRelationMemory


@dataclass(frozen=True, slots=True)
class DriftEpoch:
    epoch: int
    old_fraction: float
    new_fraction: float
    old_current_score: float
    new_current_score: float
    current_winner: str


@dataclass(frozen=True, slots=True)
class DriftReport:
    expected_change_epoch: int | None
    detected_change_epoch: int | None
    detection_delay: int | None
    false_alarms: int
    epochs: tuple[DriftEpoch, ...]


def mixed_epoch_sentences(
    source: str,
    old_partner: str,
    new_partner: str,
    new_fraction: float,
    samples: int = 100,
) -> list[str]:
    """Build a deterministic mixed epoch for controlled drift experiments."""
    if not 0.0 <= new_fraction <= 1.0:
        raise ValueError("new_fraction must be in [0, 1]")
    if samples < 1:
        raise ValueError("samples must be >= 1")
    new_count = round(samples * new_fraction)
    old_count = samples - new_count
    sentences = [f"{source} usa {old_partner} como caminho principal"] * old_count
    sentences += [f"{source} usa {new_partner} como caminho principal"] * new_count
    return sentences


def evaluate_gradual_drift(
    fractions: list[float] | tuple[float, ...],
    *,
    source: str = "rota",
    old_partner: str = "ponte",
    new_partner: str = "tunel",
    samples_per_epoch: int = 100,
    decay: float = 0.9,
) -> DriftReport:
    """Measure change detection under a gradual old->new evidence transition.

    Ground-truth change is the first epoch where the new relation is a strict
    local majority (> 0.5). Detection is the first epoch where the recency-weighted
    current score of the new relation exceeds the old one.
    """
    memory = TemporalRelationMemory(radius=3, decay=decay)
    expected = next((i for i, fraction in enumerate(fractions) if fraction > 0.5), None)
    detected: int | None = None
    false_alarms = 0
    rows: list[DriftEpoch] = []

    for epoch, fraction in enumerate(fractions):
        memory.add_epoch(
            mixed_epoch_sentences(
                source,
                old_partner,
                new_partner,
                fraction,
                samples=samples_per_epoch,
            ),
            label=f"drift-{epoch}",
        )
        old_score = memory.current_relation(source, old_partner)
        new_score = memory.current_relation(source, new_partner)
        winner = new_partner if new_score > old_score else old_partner
        if new_score > old_score and detected is None:
            if expected is not None and epoch < expected:
                false_alarms += 1
            else:
                detected = epoch
        rows.append(
            DriftEpoch(
                epoch=epoch,
                old_fraction=1.0 - fraction,
                new_fraction=fraction,
                old_current_score=old_score,
                new_current_score=new_score,
                current_winner=winner,
            )
        )

    delay = None if expected is None or detected is None else detected - expected
    return DriftReport(expected, detected, delay, false_alarms, tuple(rows))
