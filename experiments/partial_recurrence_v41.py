from memoria_resolutiva.partial_recurrence import PartialRecurrenceClassifier


def main():
    c = PartialRecurrenceClassifier()
    c.remember("A", [1.0, 0.8, 0.1, 0.0, 0.2])
    c.remember("B", [0.1, 0.2, 1.0, 0.8, 0.0])
    c.remember("C", [0.0, 0.1, 0.2, 0.4, 1.0])

    cases = {
        "A_return": [1.0, 0.79, 0.11, 0.01, 0.19],
        "A_variant": [0.85, 0.60, 0.30, 0.10, 0.35],
        "new_D": [0.0, 0.9, 0.0, 0.9, 0.0],
        "between_A_B": [0.55, 0.50, 0.55, 0.45, 0.10],
    }
    for name, vector in cases.items():
        print(name, c.classify(vector))


if __name__ == "__main__":
    main()
