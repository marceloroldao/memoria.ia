from random import Random

from memoria_resolutiva.calibration import brier_score, expected_calibration_error
from memoria_resolutiva.online_calibrator import OnlineHistogramCalibrator


def raw_probability(label: int, rng: Random) -> float:
    # Controlled compressed-confidence proxy inspired by the v0.37 failure mode.
    center = 0.58 if label else 0.44
    return min(0.99, max(0.01, rng.gauss(center, 0.07)))


def main(seed: int = 1, n: int = 5000):
    rng = Random(seed)
    labels = [rng.randrange(2) for _ in range(n)]
    raw = [raw_probability(y, rng) for y in labels]

    calibrator = OnlineHistogramCalibrator(bins=20)
    calibrated = []
    for p, y in zip(raw, labels):
        # Prequential discipline: calibrate before learning this sample's label.
        calibrated.append(calibrator.calibrate(p))
        calibrator.update(p, y)

    raw_acc = sum((p >= 0.5) == bool(y) for p, y in zip(raw, labels)) / n
    cal_acc = sum((p >= 0.5) == bool(y) for p, y in zip(calibrated, labels)) / n

    print("raw_accuracy", round(raw_acc, 6))
    print("calibrated_accuracy", round(cal_acc, 6))
    print("raw_brier", round(brier_score(raw, labels), 6))
    print("calibrated_brier", round(brier_score(calibrated, labels), 6))
    print("raw_ece", round(expected_calibration_error(raw, labels), 6))
    print("calibrated_ece", round(expected_calibration_error(calibrated, labels), 6))


if __name__ == "__main__":
    main()
