from memoria_resolutiva.stochastic_stability_v83 import evaluate


def main():
    for noise_p in (0.05, 0.10, 0.15):
        print(f"\nnoise_p={noise_p}")
        for cap in (1.25, 1.50, 2.00, 3.00):
            print(evaluate(cap, noise_p=noise_p))


if __name__ == "__main__":
    main()
