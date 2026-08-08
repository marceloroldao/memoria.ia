from memoria_resolutiva.scaling_analysis import (
    ScalingPoint,
    classify_exponent,
    empirical_memory_exponents,
    empirical_time_exponents,
    latency_growth,
)


def main():
    # Replace these illustrative measurements with outputs collected from v0.55
    # on the target machine. They exist only to exercise/report the analysis path.
    points = [
        ScalingPoint(events=10_000, elapsed_s=0.50, peak_bytes=8_000_000, items=1_000),
        ScalingPoint(events=100_000, elapsed_s=5.20, peak_bytes=78_000_000, items=10_000),
        ScalingPoint(events=1_000_000, elapsed_s=54.0, peak_bytes=760_000_000, items=100_000),
    ]

    print("events latency_us throughput_ev_s bytes_per_item")
    for p in points:
        print(p.events, round(p.latency_us, 3), round(p.throughput, 1), round(p.bytes_per_item, 1))

    print("latency_growth", [round(x, 3) for x in latency_growth(points)])
    time_exp = empirical_time_exponents(points)
    mem_exp = empirical_memory_exponents(points)
    print("time_exponents", [(round(x, 3), classify_exponent(x)) for x in time_exp])
    print("memory_exponents", [(round(x, 3), classify_exponent(x)) for x in mem_exp])


if __name__ == "__main__":
    main()
