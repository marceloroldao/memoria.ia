from memoria_resolutiva.stress_v55 import run_stress


def main():
    for events, items in [(10_000, 1_000), (100_000, 5_000), (1_000_000, 20_000)]:
        metrics = run_stress(events=events, items=items)
        print(metrics)


if __name__ == "__main__":
    main()
