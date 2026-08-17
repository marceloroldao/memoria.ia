from memoria_resolutiva.conflict_memory import ProvenanceConflictMemory


def show(label, state):
    print(label)
    print("  epoch      :", state.epoch)
    print("  scores     :", state.scores)
    print("  conflict   :", state.conflict)
    print("  winner     :", state.winner)
    print("  confidence :", round(state.confidence, 4))
    print("  sources    :", state.sources)


def main():
    memory = ProvenanceConflictMemory(decision_margin=0.20)

    memory.observe(5, "empresa_a", "diretor", "carlos", source="fonte_a", weight=1.0)
    memory.observe(5, "empresa_a", "diretor", "ana", source="fonte_b", weight=1.0)
    show("same-epoch disagreement", memory.current("empresa_a", "diretor"))

    memory2 = ProvenanceConflictMemory(decision_margin=0.20)
    memory2.observe(5, "empresa_a", "diretor", "carlos", source="blog", weight=1.0)
    memory2.observe(5, "empresa_a", "diretor", "ana", source="registro_oficial", weight=3.0)
    show("weighted evidence", memory2.current("empresa_a", "diretor"))

    memory.observe(9, "empresa_a", "diretor", "beatriz", source="registro_oficial", weight=5.0)
    show("current after later evidence", memory.current("empresa_a", "diretor"))
    show("historical conflict preserved", memory.resolve_at("empresa_a", "diretor", 5))


if __name__ == "__main__":
    main()
