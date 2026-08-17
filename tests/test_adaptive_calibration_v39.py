from memoria_resolutiva.adaptive_calibration import AdaptiveBinnedCalibrator


def test_unseen_bin_starts_neutral():
    assert AdaptiveBinnedCalibrator().predict(0.73) == 0.5


def test_window_forgets_expired_evidence():
    m = AdaptiveBinnedCalibrator(mode="window", window_size=3, bins=2)
    for y in [1, 1, 1]:
        m.update(0.8, y)
    high = m.predict(0.8)
    for y in [0, 0, 0]:
        m.update(0.8, y)
    assert m.predict(0.8) < high
    assert m.effective_mass() == 3.0


def test_decay_reduces_old_mass():
    m = AdaptiveBinnedCalibrator(mode="decay", decay=0.5, bins=2)
    m.update(0.8, 1)
    first = m.effective_mass()
    m.update(0.2, 0)
    assert m.effective_mass() < first + 1.0


def test_cumulative_retains_all_mass():
    m = AdaptiveBinnedCalibrator(mode="cumulative")
    for i in range(20):
        m.update(0.8, i % 2)
    assert m.effective_mass() == 20.0


def test_adaptive_modes_move_after_regime_reversal():
    window = AdaptiveBinnedCalibrator(mode="window", window_size=20, bins=2)
    decay = AdaptiveBinnedCalibrator(mode="decay", decay=0.9, bins=2)
    for model in (window, decay):
        for _ in range(50):
            model.update(0.8, 1)
        before = model.predict(0.8)
        for _ in range(50):
            model.update(0.8, 0)
        assert model.predict(0.8) < before
