from memoria_resolutiva.layer_clocks import MultiLayerClockSystem


def run(law: str):
    system = MultiLayerClockSystem(max_layer=5, law=law)
    for _ in range(1024):
        system.advance_all(1.0)
    return [(s.layer, s.resolution_bits, round(s.proper_time, 4)) for s in system.snapshots()]


def main():
    for law in ["exponential", "linear", "sqrt_density", "power"]:
        print(law, run(law))


if __name__ == "__main__":
    main()
