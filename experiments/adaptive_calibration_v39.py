from random import Random

from memoria_resolutiva.adaptive_calibration import AdaptiveBinnedCalibrator
from memoria_resolutiva.calibration import brier_score, expected_calibration_error


def stream(seed=12345, n1=2500, n2=2500):
    rng = Random(seed)
    for i in range(n1 + n2):
        raw = 0.05 + 0.90 * rng.random()
        # Regime 1: raw score is under-confident but directionally useful.
        if i < n1:
            true_p = 0.10 if raw < 0.5 else 0.90
        # Regime 2: environment changes; confidence becomes much softer.
        else:
            true_p = 0.40 if raw < 0.5 else 0.60
        yield i, raw, 1 if rng.random() < true_p else 0


def evaluate():
    models = {
        "cumulative": AdaptiveBinnedCalibrator(mode="cumulative"),
        "window": AdaptiveBinnedCalibrator(mode="window", window_size=300),
        "decay": AdaptiveBinnedCalibrator(mode="decay", decay=0.995),
    }
    post = {name: ([], []) for name in models}
    for i, raw, y in stream():
        for name, model in models.items():
            p = model.predict(raw)
            if i >= 2500:
                post[name][0].append(p)
                post[name][1].append(y)
            model.update(raw, y)
    for name, (p, y) in post.items():
        print(name, "post_shift_brier", round(brier_score(p, y), 6), "post_shift_ece", round(expected_calibration_error(p, y), 6))


if __name__ == "__main__":
    evaluate()
