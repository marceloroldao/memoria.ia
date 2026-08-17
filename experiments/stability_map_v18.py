from memoria_resolutiva.stability_map import build_stability_map, robust_points


def main() -> None:
    points = build_stability_map(seeds=300)
    robust = robust_points(points)

    print(f"points={len(points)} robust={len(robust)}")
    print("best robust operating points")
    for point in sorted(
        robust,
        key=lambda p: (-p.exact_detection_rate, p.false_alarm_rate, p.mean_delay or 0.0),
    )[:15]:
        print(point)

    print("\nlow-decay lag examples")
    for point in points:
        if point.decay == 0.3 and point.samples_per_epoch == 100 and point.noise == 0.0:
            print(point)


if __name__ == "__main__":
    main()
