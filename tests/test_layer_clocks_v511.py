from memoria_resolutiva.layer_clocks import LayerClock, MultiLayerClockSystem


def test_resolution_doubles_each_layer():
    s = MultiLayerClockSystem(max_layer=4)
    assert [c.resolution_bits for c in s.clocks] == [8, 16, 32, 64, 128]


def test_exponential_clock_slows_with_layer():
    s = MultiLayerClockSystem(max_layer=4, law="exponential")
    s.advance_all(64.0)
    proper = [x.proper_time for x in s.snapshots()]
    assert proper == [64.0, 32.0, 16.0, 8.0, 4.0]


def test_global_time_is_shared_while_proper_time_differs():
    s = MultiLayerClockSystem(max_layer=3, law="exponential")
    for _ in range(10):
        s.advance_all(1.0)
    states = s.snapshots()
    assert {x.global_time for x in states} == {10.0}
    assert len({x.proper_time for x in states}) == 4


def test_higher_density_never_runs_faster_for_supported_laws():
    for law in ["exponential", "linear", "sqrt_density", "power"]:
        s = MultiLayerClockSystem(max_layer=5, law=law)
        rates = [c.rate() for c in s.clocks]
        assert all(a >= b for a, b in zip(rates, rates[1:]))


def test_power_law_alpha_controls_slowdown():
    slow = LayerClock(3, law="power", alpha=1.5)
    mild = LayerClock(3, law="power", alpha=0.5)
    assert slow.rate() < mild.rate()
