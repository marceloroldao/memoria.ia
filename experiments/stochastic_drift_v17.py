from memoria_resolutiva.stochastic_drift import evaluate_stochastic_drift


def main() -> None:
    summary, _ = evaluate_stochastic_drift(
        runs=1000,
        fractions=(0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0),
        samples_per_epoch=100,
        decay=0.9,
        seed_start=0,
    )
    print(f"runs={summary.runs}")
    print(f"correct_epoch_probability={summary.correct_epoch_probability:.4f}")
    print(f"eventual_detection_probability={summary.eventual_detection_probability:.4f}")
    print(f"mean_detection_delay={summary.mean_detection_delay:.6f}")
    print(f"std_detection_delay={summary.std_detection_delay:.6f}")
    print(f"false_alarm_rate={summary.false_alarm_rate:.6f}")
    print(f"delayed_runs={summary.delayed_runs}")
    print(f"missed_runs={summary.missed_runs}")


if __name__ == "__main__":
    main()
