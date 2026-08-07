from memoria_resolutiva.temporal_memory import TemporalContextMemory

OLD = [
    "rota usa ponte para atravessar o rio",
    "motorista escolhe ponte para atravessar o rio",
    "cidade orienta trafego pela ponte principal",
] * 60

TRANSITION = [
    "rota usa tunel para atravessar o rio",
    "motorista escolhe tunel para atravessar o rio",
    "cidade orienta trafego pelo tunel principal",
] * 20

NEW = [
    "rota usa tunel para atravessar o rio",
    "motorista escolhe tunel para atravessar o rio",
    "cidade orienta trafego pelo tunel principal",
] * 80


def main() -> None:
    memory = TemporalContextMemory(radius=3, decay=0.9)
    e0 = memory.add_epoch(OLD, label="antes")
    print("epoch 0 historical:", memory.nearest_at(e0, "rota", 3))
    print("epoch 0 current   :", memory.nearest_current("rota", 3))

    e1 = memory.add_epoch(TRANSITION, label="transicao")
    print("epoch 1 current   :", memory.nearest_current("rota", 3))

    e2 = memory.add_epoch(NEW, label="agora")
    print("epoch 2 current   :", memory.nearest_current("rota", 3))
    print("old epoch preserved:", memory.nearest_at(e0, "rota", 3))

    old_score = memory.current_similarity("rota", "ponte")
    new_score = memory.current_similarity("rota", "tunel")
    print(f"current ponte={old_score:.4f} tunel={new_score:.4f} change={new_score-old_score:.4f}")


if __name__ == "__main__":
    main()
