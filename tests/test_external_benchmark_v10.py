from memoria_resolutiva.external_benchmark import SimilarityRow, evaluate_similarity_rows, spearman


def test_spearman_perfect_order():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0


def test_similarity_evaluation_reports_coverage_and_correlation():
    rows = [
        SimilarityRow("a", "b", 1.0),
        SimilarityRow("c", "d", 2.0),
        SimilarityRow("e", "f", 3.0),
    ]
    scores = {("a", "b"): 0.1, ("c", "d"): 0.5, ("e", "f"): 0.9}
    result = evaluate_similarity_rows(rows, lambda a, b: scores[(a, b)])
    assert result["coverage"] == 1.0
    assert result["spearman"] == 1.0
