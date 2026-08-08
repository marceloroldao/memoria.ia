from memoria_resolutiva.analogical_transfer import AnalogicalTransfer


def main():
    t = AnalogicalTransfer(min_similarity=0.80, min_support=2, accept_confidence=0.70)
    t.observe("A1", "requires", "validation")

    print("high similarity + support:", t.propose("A1", "B1", "requires", 0.92, independent_support=2))
    print("high similarity, weak support:", t.propose("A1", "B1", "requires", 0.92, independent_support=1))
    print("low similarity:", t.propose("A1", "C1", "requires", 0.55, independent_support=3))

    t.observe("B1", "requires", "isolation")
    print("target conflict:", t.propose("A1", "B1", "requires", 0.95, independent_support=3))


if __name__ == "__main__":
    main()
