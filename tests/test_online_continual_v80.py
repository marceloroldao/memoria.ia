from memoria_resolutiva.online_continual_v80 import DecayMemory, evaluate_regime_switch
from memoria_resolutiva.packed_lifecycle import PackedMemoryLifecycle


def test_decay_memory_rejects_invalid_decay():
    try:
        DecayMemory(0.0)
        assert False
    except ValueError:
        pass


def test_continual_probe_returns_bounded_metrics():
    r = evaluate_regime_switch("res", lambda: PackedMemoryLifecycle(levels=4), 8, 8, 8)
    assert 0.0 <= r.online_accuracy <= 1.0
    assert 0.0 <= r.post_shift_accuracy <= 1.0
    assert 0 <= r.recovery_steps <= 8
    assert r.retained_old_regime


def test_resolutive_reactivates_after_return_to_old_regime():
    r = evaluate_regime_switch("res", lambda: PackedMemoryLifecycle(levels=4), 16, 24, 24)
    assert r.reactivated_old_regime
