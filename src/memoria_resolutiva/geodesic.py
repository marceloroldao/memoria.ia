import math


def geodesic_signature(payload: bytes, time_start: int = 1) -> tuple[float, bytes]:
    bits = ''.join(f'{b:08b}' for b in payload)
    position = 0
    inclination = 0.0
    for i, bit in enumerate(bits):
        t = time_start + i
        position += 1 if bit == '0' else -1
        inclination += position / math.sqrt(t)
    anchor_len = max(1, len(payload) // 4)
    return round(inclination, 6), payload[-anchor_len:]
