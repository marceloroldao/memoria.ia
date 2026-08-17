from memoria_resolutiva.convergent_lineages import ConvergentLineageMemory


def main():
    m = ConvergentLineageMemory(convergence_threshold=0.90, ambiguity_band=0.03)
    m.remember("A", [1.0, 0.0, 0.1, 0.0])
    m.remember("A1", [0.8, 0.3, 0.2, 0.1], parent="A")
    m.remember("B", [0.0, 1.0, 0.0, 0.1])
    m.remember("B1", [0.75, 0.35, 0.2, 0.1], parent="B")

    decision = m.compare("A1", "B1")
    print("decision", decision)
    print("ancestry_A1", m.ancestry("A1"))
    print("ancestry_B1", m.ancestry("B1"))
    if decision.macro_concept:
        print("macro_members", m.members(decision.macro_concept))


if __name__ == "__main__":
    main()
