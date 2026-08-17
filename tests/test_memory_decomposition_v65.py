from memoria_resolutiva.memory_decomposition_v65 import run_workload


def test_memory_decomposition_reports_positive_costs():
    events = [("x", True, 1.0)] * 8 + [("x", False, 1.0)] * 8
    row = run_workload(events, items=1, levels=3)
    assert row.events == 16
    assert row.items == 1
    assert row.peak_bytes > 0
    assert row.bytes_per_item > 0
    assert row.transitions > 0
    assert row.bytes_per_transition > 0
