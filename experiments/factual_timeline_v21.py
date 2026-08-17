from memoria_resolutiva.factual_timeline import FactualTimelineMemory


def main():
    memory = FactualTimelineMemory()
    subject = "empresa_a"
    relation = "diretor"

    memory.observe(1, subject, relation, "joao", "registro_t1")
    memory.observe(5, subject, relation, "carlos", "registro_t5")
    memory.observe(9, subject, relation, "ana", "registro_t9")

    print("history:", [(e.epoch, e.value) for e in memory.history(subject, relation)])
    print("current:", memory.current(subject, relation).value)
    print("at t1:", memory.at(subject, relation, 1).value)
    print("at t7:", memory.at(subject, relation, 7).value)
    print("carlos superseded at:", memory.superseded_at(subject, relation, "carlos"))
    print("transitions:", [(a.value, b.value, b.epoch) for a, b in memory.transitions(subject, relation)])


if __name__ == "__main__":
    main()
