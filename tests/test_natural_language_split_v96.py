from experiments.natural_language_split_v96 import CALIBRATION, TEST, TRAIN, build, evaluate


def test_train_calibration_test_are_textually_disjoint():
    train_text = {s for rows in TRAIN.values() for s in rows}
    calibration_text = {s for _, s in CALIBRATION}
    test_text = {s for _, s in TEST}
    assert train_text.isdisjoint(calibration_text)
    assert train_text.isdisjoint(test_text)
    assert calibration_text.isdisjoint(test_text)


def test_confusion_evaluator_counts_every_row():
    router = build(0.10, 0.07)
    metrics, matrix, outputs = evaluate(router, TEST)
    assert len(outputs) == len(TEST)
    assert sum(sum(row.values()) for row in matrix.values()) == len(TEST)
    assert 0.0 <= metrics.accuracy <= 1.0
    assert 0.0 <= metrics.positive_recall <= 1.0
    assert 0.0 <= metrics.false_positive_rate <= 1.0
    assert 0.0 <= metrics.abstention_rate <= 1.0
    assert 0.0 <= metrics.wrong_known_class_rate <= 1.0
