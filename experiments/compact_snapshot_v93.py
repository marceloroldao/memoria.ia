from memoria_resolutiva.routed_lifecycle import RoutedLifecycleMemory
from memoria_resolutiva.routed_persistence import encode_routed_snapshot
from memoria_resolutiva.routed_persistence_compact import encode_compact_routed_snapshot, decode_compact_routed_snapshot


def build(concepts: int, routes_per: int = 4):
    m = RoutedLifecycleMemory(levels=5, max_strength=1.25)
    for i in range(concepts):
        kid = f"k{i}"
        payload = {"concept": i, "facts": list(range(8))}
        for r in range(routes_per):
            route = ("private" if r < 2 else "collective", f"agent-{r % 3}", f"mod-{r}", kid)
            m.register(kid, payload, route, modality=f"mod-{r}", provenance=f"agent-{r % 3}")
            for _ in range(32):
                m.support(route)
            if r == 0 and i % 3 == 0:
                for _ in range(24):
                    m.contradict(route)
    return m


def main():
    for concepts in (100, 500, 1000, 5000):
        m = build(concepts)
        verbose = encode_routed_snapshot(m)
        compact = encode_compact_routed_snapshot(m)
        restored = decode_compact_routed_snapshot(compact)
        assert restored.knowledge.knowledge_count == m.knowledge.knowledge_count
        assert restored.knowledge.route_count == m.knowledge.route_count
        print({
            "concepts": concepts,
            "routes": m.knowledge.route_count,
            "json_bytes": len(verbose),
            "compact_bytes": len(compact),
            "reduction": 1.0 - len(compact) / len(verbose),
            "compact_bytes_per_route": len(compact) / m.knowledge.route_count,
        })


if __name__ == "__main__":
    main()
