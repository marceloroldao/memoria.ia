from __future__ import annotations

from dataclasses import dataclass
from random import Random

from .polysemy import PolysemyMemory


@dataclass(frozen=True, slots=True)
class StabilityRun:
    name: str
    sense_count: int
    finance_sense: int | None
    data_sense: int | None
    separated: bool


@dataclass(frozen=True, slots=True)
class StabilitySummary:
    runs: tuple[StabilityRun, ...]
    separation_rate: float
    median_sense_count: float


def _median(values: list[int]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def evaluate_polysemy_order_stability(
    finance: list[str],
    data: list[str],
    *,
    window: int = 3,
    split_threshold: float = 0.18,
    shuffled_runs: int = 20,
    seed: int = 0,
) -> StabilitySummary:
    """Evaluate whether sense separation survives different observation orders."""
    orders: list[tuple[str, list[str]]] = [
        ("finance_first", finance + data),
        ("data_first", data + finance),
        ("alternating", [x for pair in zip(finance, data) for x in pair] + finance[len(data):] + data[len(finance):]),
    ]

    rng = Random(seed)
    all_items = finance + data
    for i in range(shuffled_runs):
        shuffled = list(all_items)
        rng.shuffle(shuffled)
        orders.append((f"shuffle_{i}", shuffled))

    runs: list[StabilityRun] = []
    finance_context = {"credito", "cliente", "emprestimo", "conta", "juros", "deposito"}
    data_context = {"dados", "registros", "servidor", "tabelas", "consulta", "aplicacao"}

    for name, sentences in orders:
        memory = PolysemyMemory(window=window, split_threshold=split_threshold)
        for sentence in sentences:
            memory.observe(sentence)
        finance_id, _ = memory.resolve("banco", finance_context)
        data_id, _ = memory.resolve("banco", data_context)
        runs.append(
            StabilityRun(
                name=name,
                sense_count=len(memory.senses("banco")),
                finance_sense=finance_id,
                data_sense=data_id,
                separated=(finance_id is not None and data_id is not None and finance_id != data_id),
            )
        )

    separation_rate = sum(r.separated for r in runs) / len(runs) if runs else 0.0
    return StabilitySummary(
        runs=tuple(runs),
        separation_rate=separation_rate,
        median_sense_count=_median([r.sense_count for r in runs]),
    )
