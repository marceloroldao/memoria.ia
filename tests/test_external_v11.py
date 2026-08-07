from memoria_resolutiva.external_benchmark import SimilarityRow, evaluate_similarity_rows, spearman


def test_spearman_extremes():
    assert spearman([1.0, 2.0, 3.0], [10.0, 20.0, 30.0]) > 0.999
    assert spearman([1.0, 2.0, 3.0], [30.0, 20.0, 10.0]) < -0.999


def test_explicit_coverage_does_not_confuse_zero_similarity_with_oov():
    rows = [
        SimilarityRow("a", "b", 1.0),
        SimilarityRow("a", "c", 0.0),
        SimilarityRow("a", "missing", 0.5),
    ]
    vocab = {"a", "b", "c"}
    scores = {("a", "b"): 0.8, ("a", "c"): 0.0}

    result = evaluate_similarity_rows(
        rows,
        lambda x, y: scores.get((x, y), 0.0),
        contains=lambda word: word in vocab,
    )

    assert result["covered_pairs"] == 2.0
    assert result["coverage"] == 2 / 3


def test_similarity_evaluation_uses_only_covered_pairs_when_vocabulary_is_explicit():
    rows = [
        SimilarityRow("a", "b", 1.0),
        SimilarityRow("c", "d", 2.0),
        SimilarityRow("x", "y", 99.0),
    ]
    vocab = {"a", "b", "c", "d"}
    model = {("a", "b"): 0.1, ("c", "d"): 0.9}

    result = evaluate_similarity_rows(
        rows,
        lambda x, y: model.get((x, y), 0.0),
        contains=lambda word: word in vocab,
    )

    assert result["coverage"] == 2 / 3
    assert result["spearman"] > 0.999
