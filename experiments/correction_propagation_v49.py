from memoria_resolutiva.correction_propagation import CorrectionGraph


def main():
    g = CorrectionGraph()
    g.add_node("obs_A", "A is true")
    g.add_node("obs_B", "B is true")
    g.add_node("h1", "A implies X", parents={"obs_A"})
    g.add_node("h2", "X and B imply Y", parents={"h1", "obs_B"})
    g.add_node("h3", "Y implies Z", parents={"h2"})
    g.add_node("unrelated", "Q", parents={"obs_B"})

    print("affected by obs_A correction:", g.correct("obs_A", "A is false"))
    print("obs_A history:", g.nodes["obs_A"].history)
    print("h3 lineage:", sorted(g.lineage("h3")))
    print("unrelated affected?", "unrelated" in g.affected_descendants("obs_A"))


if __name__ == "__main__":
    main()
