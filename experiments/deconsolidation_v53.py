from memoria_resolutiva.deconsolidation import DeconsolidationMemory


def main():
    m = DeconsolidationMemory(layers=4, deactivate_threshold=0.25)
    m.seed_consolidated("regra_antiga", [0.8, 0.8, 0.8, 0.8])
    print("initial", m.snapshot("regra_antiga"))

    for step in range(1, 9):
        m.contradict("regra_antiga", amount=0.15)
        print(step, m.active_layers("regra_antiga"), [round(s["strength"], 3) for s in m.snapshot("regra_antiga")])

    for step in range(1, 5):
        m.reinforce("regra_antiga", amount=0.2)
        print("reinforce", step, m.active_layers("regra_antiga"))


if __name__ == "__main__":
    main()
