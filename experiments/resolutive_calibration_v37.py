from memoria_resolutiva.resolutive_calibration import evaluate_resolutive_calibration, resolutive_reliability


def main():
    result = evaluate_resolutive_calibration(seed=123, n=5000, bins=10)
    print(result)
    for bucket in resolutive_reliability(seed=123, n=5000, bins=10):
        print(bucket)


if __name__ == "__main__":
    main()
