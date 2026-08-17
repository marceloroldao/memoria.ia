from memoria_resolutiva.baseline_benchmark import HashMemory, ChronologicalMemory
from memoria_resolutiva.measured_capability import measure_capabilities
from memoria_resolutiva.memory_lifecycle import MemoryLifecycle


def test_measurement_is_bounded_for_all_baselines():
    factories = [HashMemory, ChronologicalMemory, lambda: MemoryLifecycle(levels=5)]
    for factory in factories:
        m = measure_capabilities(factory)
        for value in (m.retention, m.noise_resistance, m.regime_adaptation, m.reactivation):
            assert 0.0 <= value <= 1.0


def test_hash_retains_after_unrelated_traffic():
    m = measure_capabilities(HashMemory)
    assert m.retention == 1.0


def test_chronological_memory_can_reactivate():
    m = measure_capabilities(ChronologicalMemory)
    assert m.reactivation == 1.0


def test_resolutive_lifecycle_preserves_historical_knowledge():
    m = measure_capabilities(lambda: MemoryLifecycle(levels=5))
    assert m.retention == 1.0
    assert m.reactivation == 1.0
