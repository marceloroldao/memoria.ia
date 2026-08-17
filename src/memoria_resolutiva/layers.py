from dataclasses import dataclass


def layer_bits(layer: int) -> int:
    if layer < 0:
        raise ValueError("layer must be >= 0")
    return 8 * (2 ** layer)


@dataclass(frozen=True, slots=True)
class LayerSpec:
    level: int

    @property
    def bits(self) -> int:
        return layer_bits(self.level)

    @property
    def bytes(self) -> int:
        return self.bits // 8
