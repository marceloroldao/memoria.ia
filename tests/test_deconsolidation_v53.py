from memoria_resolutiva.deconsolidation import DeconsolidationMemory


def test_contradiction_weakens_shallow_layers_faster():
    m = DeconsolidationMemory(layers=4, deactivate_threshold=0.25)
    m.seed_consolidated("x", [0.8, 0.8, 0.8, 0.8])
    m.contradict("x", amount=0.2)
    s = m.snapshot("x")
    assert s[0]["strength"] < s[1]["strength"] < s[2]["strength"] < s[3]["strength"]


def test_deactivation_preserves_history():
    m = DeconsolidationMemory(layers=2, deactivate_threshold=0.25)
    m.seed_consolidated("x", [0.3, 0.8])
    m.contradict("x", amount=0.1)
    snap = m.snapshot("x")
    assert snap[0]["active"] is False
    assert snap[0]["history"]


def test_deep_layer_survives_longer_under_same_contradiction_stream():
    m = DeconsolidationMemory(layers=3, deactivate_threshold=0.25)
    m.seed_consolidated("x", [0.5, 0.5, 0.5])
    for _ in range(4):
        m.contradict("x", amount=0.15)
    active = m.active_layers("x")
    assert 0 not in active
    assert 2 in active


def test_reinforcement_can_reactivate_without_erasing_old_state():
    m = DeconsolidationMemory(layers=1, deactivate_threshold=0.25)
    m.seed_consolidated("x", [0.3])
    m.contradict("x", amount=0.1)
    assert m.active_layers("x") == []
    old_history_len = len(m.snapshot("x")[0]["history"])
    m.reinforce("x", amount=0.2)
    assert m.active_layers("x") == [0]
    assert len(m.snapshot("x")[0]["history"]) > old_history_len
