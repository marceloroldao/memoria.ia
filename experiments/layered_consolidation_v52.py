from memoria_resolutiva.layered_consolidation import LayeredConsolidationMemory


def main():
    m = LayeredConsolidationMemory(layers=5, persistence_threshold=2.0, decay_per_global_step=0.15)

    # transient event: appears briefly, then disappears
    for _ in range(2):
        m.observe("ruido_transitorio")
    for _ in range(8):
        m.advance_without_observation()

    # persistent pattern: repeated long enough to cross slower clocks
    for _ in range(40):
        m.observe("padrao_persistente")

    print("global_time", m.global_time)
    print("transient_layers", m.accepted_layers("ruido_transitorio"))
    print("persistent_layers", m.accepted_layers("padrao_persistente"))
    for state in m.state():
        print(state)


if __name__ == "__main__":
    main()
