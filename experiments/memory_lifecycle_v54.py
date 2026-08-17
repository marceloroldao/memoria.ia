from memoria_resolutiva.memory_lifecycle import MemoryLifecycle


def main():
    m = MemoryLifecycle(levels=5)
    key = "persistent_pattern"

    # Phase 1: persistent evidence consolidates deeply.
    for _ in range(40):
        m.support(key)
    print("after consolidation", m.active_depth(key), m.snapshot(key))

    # Phase 2: prolonged contradiction reduces functional depth.
    for _ in range(35):
        m.contradict(key)
    print("after contradiction", m.active_depth(key), m.historical_depth(key), m.snapshot(key))

    # Phase 3: old pattern returns; history remains and layers can reactivate.
    for _ in range(40):
        m.support(key)
    print("after recurrence", m.active_depth(key), m.historical_depth(key), m.snapshot(key))

    # Noise should not reach deep layers.
    noise = "transient_noise"
    m.support(noise)
    print("noise", m.active_depth(noise), m.historical_depth(noise), m.snapshot(noise))


if __name__ == "__main__":
    main()
