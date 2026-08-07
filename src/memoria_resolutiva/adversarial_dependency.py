from __future__ import annotations

from dataclasses import dataclass
from .dependency_inference import SourceDocument, infer_dependency_graph, roots_by_source


@dataclass(frozen=True, slots=True)
class AdversarialDependencyReport:
    true_edges: int
    predicted_edges: int
    true_positive_edges: int
    precision: float
    recall: float
    false_positive_edges: int
    false_negative_edges: int


def evaluate_dependency_edges(
    documents: list[SourceDocument],
    true_parent: dict[str, str | None],
    *,
    threshold: float = 0.72,
) -> AdversarialDependencyReport:
    graph = infer_dependency_graph(documents, threshold=threshold)
    predicted = {source: parent for source, parent in graph.items() if parent is not None}
    truth = {source: parent for source, parent in true_parent.items() if parent is not None}

    tp = sum(1 for source, parent in predicted.items() if truth.get(source) == parent)
    fp = len(predicted) - tp
    fn = len(truth) - tp
    precision = tp / len(predicted) if predicted else 1.0
    recall = tp / len(truth) if truth else 1.0
    return AdversarialDependencyReport(
        true_edges=len(truth),
        predicted_edges=len(predicted),
        true_positive_edges=tp,
        precision=precision,
        recall=recall,
        false_positive_edges=fp,
        false_negative_edges=fn,
    )


def inferred_root_count(documents: list[SourceDocument], threshold: float = 0.72) -> int:
    graph = infer_dependency_graph(documents, threshold=threshold)
    roots = roots_by_source(graph)
    return len(set(roots.values()))
