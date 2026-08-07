from memoria_resolutiva.regime_speciation import RegimeLineageMemory


def main():
    m = RegimeLineageMemory(variant_threshold=0.90, speciation_threshold=0.75, persistence=2)
    m.remember_root("A", [1.0, 0.8, 0.1, 0.0])

    sequence = [
        ("A1", [0.96, 0.76, 0.14, 0.04]),
        ("A2", [0.86, 0.64, 0.26, 0.12]),
        ("A3", [0.66, 0.46, 0.46, 0.30]),
        ("A4", [0.58, 0.38, 0.54, 0.38]),
    ]

    for name, profile in sequence:
        state = m.observe_variant("A", profile, child_name=name)
        print(name, state)

    print("events", m.events)
    for event in m.events:
        print("lineage", event.child, m.lineage(event.child))


if __name__ == "__main__":
    main()
