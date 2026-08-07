from memoria_resolutiva.drift_baselines import compare_detectors


def main() -> None:
    for samples in (10, 30, 100):
        for noise in (0.0, 0.1, 0.25):
            summaries = compare_detectors(
                seeds=1000,
                samples_per_epoch=samples,
                noise=noise,
                decay=0.9,
            )
            print(f"samples={samples} noise={noise}")
            for summary in summaries:
                print(
                    f"  {summary.name:14s} exact={summary.exact_rate:.3f} "
                    f"detect={summary.detection_rate:.3f} "
                    f"false_alarm={summary.false_alarm_rate:.3f} "
                    f"mean_delay={summary.mean_delay}"
                )


if __name__ == "__main__":
    main()
