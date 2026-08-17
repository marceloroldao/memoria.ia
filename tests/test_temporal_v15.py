from memoria_resolutiva.temporal_memory import TemporalRelationMemory

CANDIDATES = ("ponte", "tunel", "balsa")


def _sentences(partner: str):
    return [
        f"rota usa {partner} para atravessar",
        f"rota segue por {partner} durante viagem",
    ] * 20


def test_timeline_preserves_oscillating_history_and_detects_changes():
    memory = TemporalRelationMemory(radius=3, decay=1.0)
    sequence = ["ponte", "tunel", "ponte", "balsa", "balsa", "tunel"]
    for i, partner in enumerate(sequence):
        memory.add_epoch(_sentences(partner), label=f"e{i}")

    timeline = memory.timeline("rota", CANDIDATES)
    assert [item.candidate for item in timeline if item is not None] == sequence

    changes = memory.detect_changes("rota", CANDIDATES)
    assert [change.epoch for change in changes] == [0, 1, 2, 3, 5]
    assert [change.current for change in changes] == ["ponte", "tunel", "ponte", "balsa", "tunel"]

    assert memory.dominant_at(0, "rota", CANDIDATES).candidate == "ponte"
    assert memory.dominant_at(3, "rota", CANDIDATES).candidate == "balsa"
    assert memory.dominant_current("rota", CANDIDATES).candidate == "tunel"
