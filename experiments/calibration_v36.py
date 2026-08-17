from random import Random

from memoria_resolutiva.calibration import brier_score, expected_calibration_error, reliability_bins


def synthetic_trials(seed: int = 12345, n: int = 5000):
    """Controlled calibration benchmark with known Bernoulli ground truth."""
    rng = Random(seed)
    confidences = []
    outcomes = []
    for _ in range(n):
        # Spread known probabilities through [0.05, 0.95].
        p = 0.05 + 0.90 * rng.random()
        y = 1 if rng.random() < p else 0
        confidences.append(p)
        outcomes.append(y)
    return confidences, outcomes


def main():
    p, y = synthetic_trials()
    print("n", len(p))
    print("brier", round(brier_score(p, y), 6))
    print("ece", round(expected_calibration_error(p, y, bins=10), 6))
    for b in reliability_bins(p, y, bins=10):
        print(b)


if __name__ == "__main__":
    main()
