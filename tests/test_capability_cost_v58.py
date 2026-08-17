from memoria_resolutiva.capability_cost import CapabilityScore, CostScore, normalized_cost, utility_per_cost


def test_quality_is_mean_of_capabilities():
    c = CapabilityScore(1.0, 0.0, 1.0, 0.0)
    assert c.quality == 0.5


def test_reference_cost_normalizes_to_one():
    cost = CostScore(latency_us=2.0, peak_bytes=100)
    assert normalized_cost(cost, 2.0, 100) == 1.0


def test_more_capability_at_same_cost_improves_utility():
    cost = CostScore(2.0, 100)
    low = CapabilityScore(0.2, 0.2, 0.2, 0.2)
    high = CapabilityScore(0.8, 0.8, 0.8, 0.8)
    assert utility_per_cost(high, cost, 2.0, 100) > utility_per_cost(low, cost, 2.0, 100)


def test_more_cost_at_same_capability_reduces_utility():
    cap = CapabilityScore(0.8, 0.8, 0.8, 0.8)
    cheap = CostScore(1.0, 100)
    expensive = CostScore(10.0, 1000)
    assert utility_per_cost(cap, cheap, 1.0, 100) > utility_per_cost(cap, expensive, 1.0, 100)
