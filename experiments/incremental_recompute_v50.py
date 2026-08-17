from memoria_resolutiva.incremental_recompute import IncrementalRecomputeGraph


def build_graph():
    g = IncrementalRecomputeGraph()
    g.add_root("R1", 1.0)
    g.add_root("R2", 0.4)
    g.add_derived("A", ["R1"])
    g.add_derived("B", ["A"])
    g.add_derived("C", ["B", "R2"])
    g.add_derived("U", ["R2"])
    return g


def main():
    g = build_graph()
    touched = g.update_root_incremental("R1", 0.2)
    incremental = g.snapshot()
    full_touched = g.full_recompute()
    full = g.snapshot()
    print("incremental touched", touched)
    print("full touched", full_touched)
    print("same final state", incremental == full)
    print("snapshot", full)


if __name__ == "__main__":
    main()
