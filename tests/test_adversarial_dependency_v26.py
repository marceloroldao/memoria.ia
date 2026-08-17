from memoria_resolutiva.adversarial_dependency import evaluate_dependency_edges
from memoria_resolutiva.dependency_inference import SourceDocument


def _docs_and_truth():
    docs = [
        SourceDocument("origem", 1, "novo imposto especial sobre fibra optica foi anunciado pelo governo", cites=()),
        SourceDocument("copy_easy", 2, "governo anunciou novo imposto especial sobre fibra optica", cites=()),
        SourceDocument("copy_hard", 5, "autoridades criaram cobranca adicional para conexoes de internet por fibra", cites=()),
        SourceDocument("independente", 3, "diario oficial nao registra nova tributacao especifica para fibra", cites=()),
    ]
    truth = {
        "origem": None,
        "copy_easy": "origem",
        "copy_hard": "origem",
        "independente": None,
    }
    return docs, truth


def test_metrics_are_bounded():
    docs, truth = _docs_and_truth()
    report = evaluate_dependency_edges(docs, truth, threshold=0.72)
    assert 0.0 <= report.precision <= 1.0
    assert 0.0 <= report.recall <= 1.0
    assert report.true_edges == 2


def test_easy_copy_is_detectable_at_relaxed_threshold():
    docs, truth = _docs_and_truth()
    report = evaluate_dependency_edges(docs, truth, threshold=0.55)
    assert report.true_positive_edges >= 1


def test_strong_paraphrase_can_reduce_recall():
    docs, truth = _docs_and_truth()
    strict = evaluate_dependency_edges(docs, truth, threshold=0.80)
    relaxed = evaluate_dependency_edges(docs, truth, threshold=0.55)
    assert relaxed.recall >= strict.recall


def test_threshold_exposes_precision_recall_tradeoff():
    docs, truth = _docs_and_truth()
    low = evaluate_dependency_edges(docs, truth, threshold=0.45)
    high = evaluate_dependency_edges(docs, truth, threshold=0.80)
    assert low.predicted_edges >= high.predicted_edges
