from __future__ import annotations

import secrets
from time import perf_counter

from memoria_resolutiva.routed_lifecycle import RoutedLifecycleMemory
from memoria_resolutiva.routed_persistence import encode_routed_snapshot
from memoria_resolutiva.routed_persistence_compact import (
    decode_compact_routed_snapshot,
    encode_compact_routed_snapshot,
)


def build(n_knowledge: int, routes_per: int = 4, payload_bytes: int = 256):
    m = RoutedLifecycleMemory(levels=5, max_strength=1.25)
    routes = []
    for i in range(n_knowledge):
        payload = {"blob": secrets.token_hex(payload_bytes // 2), "index": i}
        kid = f"k{i}"
        for r in range(routes_per):
            route = ("private" if r < 2 else "collective", f"agent-{r%3}", f"mod-{r}", kid)
            m.register(kid, payload, route, modality=f"mod-{r}", provenance=f"agent-{r%3}")
            routes.append(route)
            for _ in range(16):
                m.support(route)
    return m, routes


def measure(n_knowledge: int):
    m, routes = build(n_knowledge)
    t0 = perf_counter(); verbose = encode_routed_snapshot(m); t1 = perf_counter()
    compact = encode_compact_routed_snapshot(m); t2 = perf_counter()
    restored = decode_compact_routed_snapshot(compact); t3 = perf_counter()
    probe = routes[len(routes)//2]
    assert restored.status(probe) == m.status(probe)
    return {
        "knowledge": n_knowledge,
        "routes": len(routes),
        "verbose_bytes": len(verbose),
        "compact_bytes": len(compact),
        "reduction": 1.0 - len(compact)/len(verbose),
        "verbose_encode_ms": (t1-t0)*1000,
        "compact_encode_ms": (t2-t1)*1000,
        "compact_decode_ms": (t3-t2)*1000,
        "compact_bytes_per_route": len(compact)/len(routes),
    }


if __name__ == "__main__":
    for n in (100, 500, 1000, 5000):
        print(measure(n))
