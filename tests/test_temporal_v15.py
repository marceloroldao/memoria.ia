from memoria_resolutiva.temporal_memory import TemporalContextMemory


def _sentences(partner: str):
    return [
        f"rota usa {partner} para atravessar",
        f"motorista escolhe {partner} para atravessar",
    ] * 20


def test_timeline_preserves_oscillating_history_and_detects_changes():
    memory = TemporalContextMemory(radius=2, decay=1.0)
    sequence = ["ponte", "tunel", "ponte", "balsa", "balsa", "tunel"]
    for i, partner in enumerate(sequence):
        memory.add_epoch(_sentences(partner), label=f"e{i}")

    timeline = memory.timeline("rota")
    assert [item.candidate for item in timeline if item is not None] == sequence

    changes = memory.detect_changes("rota")
    assert [change.epoch for change in changes] == [0, 1, 2, 3, 5]
    assert [change.current for change in changes] == ["ponte", "tunel", "ponte", "balsa", "tunel"]

    assert memory.dominant_at(0, "rota").candidate == "ponte"
    assert memory.dominant_at(3, "rota").candidate == "balsa"
    assert memory.dominant_current("rota").candidate == "tunel"
