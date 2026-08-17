from memoria_resolutiva.temporal_memory import TemporalRelationMemory

CANDIDATES = ("ponte", "tunel", "balsa")


def epoch_sentences(partner: str, repeat: int = 40) -> list[str]:
    return [
        f"rota usa {partner} para atravessar o rio",
        f"rota segue por {partner} durante a viagem",
        f"rota passa pela {partner} antes do destino",
    ] * repeat


def main() -> None:
    memory = TemporalRelationMemory(radius=3, decay=0.9)
    sequence = [
        ("ponte", "fase-a"),
        ("tunel", "fase-b"),
        ("ponte", "fase-c"),
        ("balsa", "fase-d"),
        ("balsa", "fase-e"),
        ("tunel", "fase-f"),
    ]

    for partner, label in sequence:
        memory.add_epoch(epoch_sentences(partner), label=label)

    print("timeline")
    for epoch, item in enumerate(memory.timeline("rota", CANDIDATES)):
        print(epoch, memory.epoch_labels[epoch], item)

    print("changes")
    for change in memory.detect_changes("rota", CANDIDATES):
        print(change)

    print("current", memory.dominant_current("rota", CANDIDATES))
    print("historical epoch 0", memory.dominant_at(0, "rota", CANDIDATES))
    print("historical epoch 3", memory.dominant_at(3, "rota", CANDIDATES))


if __name__ == "__main__":
    main()
