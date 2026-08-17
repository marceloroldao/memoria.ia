from memoria_resolutiva.layered_consolidation import LayeredConsolidationMemory


def test_proper_time_slows_with_layer_depth():
    m = LayeredConsolidationMemory(layers=5)
    m.observe("x", dt=64)
    assert m.proper_time == [64.0, 32.0, 16.0, 8.0, 4.0]


def test_transient_signal_stays_shallow():
    m = LayeredConsolidationMemory(layers=4, persistence_threshold=2.0, decay_per_global_step=0.2)
    m.observe("noise")
    m.advance_without_observation(10)
    assert m.accepted_layers("noise") == (0,)


def test_persistent_signal_consolidates_deeper_than_transient():
    m = LayeredConsolidationMemory(layers=5, persistence_threshold=2.0, decay_per_global_step=0.05)
    for _ in range(40):
        m.observe("persistent")
    layers = m.accepted_layers("persistent")
    assert layers[0] == 0
    assert len(layers) >= 3


def test_deeper_layers_require_more_global_exposure():
    m = LayeredConsolidationMemory(layers=4, persistence_threshold=1.5, decay_per_global_step=0.0)
    for _ in range(3):
        m.observe("x")
    early = m.accepted_layers("x")
    for _ in range(12):
        m.observe("x")
    late = m.accepted_layers("x")
    assert len(late) > len(early)


def test_global_time_and_proper_time_are_distinct():
    m = LayeredConsolidationMemory(layers=3)
    m.observe("x", dt=8)
    assert m.global_time == 8.0
    assert m.proper_time[0] == 8.0
    assert m.proper_time[1] == 4.0
    assert m.proper_time[2] == 2.0
