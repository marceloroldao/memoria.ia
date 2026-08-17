from memoria_resolutiva.stability_plasticity_v82 import sweep_frontier


def main():
    for row in sweep_frontier():
        print(row)


if __name__ == "__main__":
    main()
