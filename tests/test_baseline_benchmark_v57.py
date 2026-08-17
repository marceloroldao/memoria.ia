from memoria_resolutiva.baseline_benchmark import HashMemory, ChronologicalMemory, benchmark
from memoria_resolutiva.memory_lifecycle import MemoryLifecycle


def events():
    return [("x", True, 1.0), ("x", True, 1.0), ("x", False, 0.5), ("y", True, 1.0)]


def test_hash_memory_tracks_net_strength():
    m = HashMemory()
    for k, p, a in events():
        (m.support if p else m.contradict)(k, a)
    assert m.data["x"] == 1.5


def test_chronological_memory_preserves_event_log():
    m = ChronologicalMemory()
    for k, p, a in events():
        (m.support if p else m.contradict)(k, a)
    assert len(m.events) == 4
    assert m.score("x") == 1.5


def test_benchmark_reports_all_events():
    r = benchmark("hash", HashMemory(), events())
    assert r.events == 4
    assert r.seconds >= 0.0
    assert r.peak_bytes >= 0


def test_resolutive_and_baselines_accept_same_event_protocol():
    sequence = events()
    for name, memory in [("hash", HashMemory()), ("chronological", ChronologicalMemory()), ("resolutive", MemoryLifecycle(levels=4))]:
        r = benchmark(name, memory, sequence)
        assert r.events == len(sequence)
