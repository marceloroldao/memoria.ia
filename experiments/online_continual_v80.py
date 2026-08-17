from memoria_resolutiva.online_continual_v80 import default_factories, evaluate_regime_switch


def main():
    for stable, shift, ret in [(16, 16, 16), (32, 32, 32), (64, 64, 64)]:
        print(f"\nA={stable} B={shift} A2={ret}")
        for name, factory in default_factories().items():
            print(evaluate_regime_switch(name, factory, stable, shift, ret))


if __name__ == "__main__":
    main()
