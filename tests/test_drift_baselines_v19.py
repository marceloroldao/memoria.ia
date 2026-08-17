from math import exp

from memoria_resolutiva.drift_baselines import compare_detectors


def test_matched_ewma_tracks_exponential_resolutive_detector_closely():
    resolutive, ewma, _ = compare_detectors(
        seeds=200,
        samples_per_epoch=100,
        noise=0.0,
        decay=0.9,
        ewma_alpha=1.0 - exp(-0.9),
    )
    assert abs(resolutive.exact_rate - ewma.exact_rate) <= 0.02
    assert abs((resolutive.mean_delay or 0.0) - (ewma.mean_delay or 0.0)) <= 0.05


def test_cusum_is_more_conservative_in_reference_protocol():
    resolutive, _, cusum = compare_detectors(
        seeds=200,
        samples_per_epoch=100,
        noise=0.0,
        decay=0.9,
    )
    assert resolutive.mean_delay is not None
    assert cusum.mean_delay is not None
    assert cusum.mean_delay > resolutive.mean_delay
