from memoria_resolutiva.capability_cost import CapabilityScore, CostScore, utility_per_cost


def main():
    # Placeholder benchmark records used only to exercise the scoring pipeline.
    # Replace with measured v0.55/v0.57 outputs for publication-grade comparison.
    systems = {
        "hash": (
            CapabilityScore(retention=0.55, noise_resistance=0.40, regime_adaptation=0.50, reactivation=0.10),
            CostScore(latency_us=1.0, peak_bytes=1_000_000),
        ),
        "chronological": (
            CapabilityScore(retention=0.80, noise_resistance=0.45, regime_adaptation=0.55, reactivation=0.40),
            CostScore(latency_us=4.0, peak_bytes=4_000_000),
        ),
        "resolutive": (
            CapabilityScore(retention=0.90, noise_resistance=0.85, regime_adaptation=0.82, reactivation=0.88),
            CostScore(latency_us=6.0, peak_bytes=6_000_000),
        ),
    }
    latency_ref = min(cost.latency_us for _, cost in systems.values())
    memory_ref = min(cost.peak_bytes for _, cost in systems.values())
    for name, (cap, cost) in systems.items():
        print(name, "quality", round(cap.quality, 4), "utility_per_cost", round(utility_per_cost(cap, cost, latency_ref, memory_ref), 6))


if __name__ == "__main__":
    main()
