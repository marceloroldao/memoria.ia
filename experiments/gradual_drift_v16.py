from memoria_resolutiva.gradual_drift import evaluate_gradual_drift


def main() -> None:
    fractions = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
    report = evaluate_gradual_drift(fractions, decay=0.9, samples_per_epoch=100)

    for row in report.epochs:
        print(
            f"epoch={row.epoch} old={row.old_fraction:.2f} new={row.new_fraction:.2f} "
            f"old_score={row.old_current_score:.4f} new_score={row.new_current_score:.4f} "
            f"winner={row.current_winner}"
        )

    print(
        f"expected={report.expected_change_epoch} detected={report.detected_change_epoch} "
        f"delay={report.detection_delay} false_alarms={report.false_alarms}"
    )


if __name__ == "__main__":
    main()
