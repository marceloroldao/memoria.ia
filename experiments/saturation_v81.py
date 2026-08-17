from memoria_resolutiva.online_continual_v80 import evaluate_regime_switch
from memoria_resolutiva.saturating_lifecycle_v81 import SaturatingPackedMemoryLifecycle


def main():
    for saturation in (1.5, 2.0, 3.0, 4.0, 8.0):
        row = evaluate_regime_switch(
            f"sat_{saturation}",
            lambda s=saturation: SaturatingPackedMemoryLifecycle(levels=5, saturation=s),
            32, 32, 32,
        )
        print(row)


if __name__ == "__main__":
    main()
