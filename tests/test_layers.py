from memoria_resolutiva.layers import layer_bits


def test_layer_rule():
    assert [layer_bits(i) for i in range(4)] == [8, 16, 32, 64]
