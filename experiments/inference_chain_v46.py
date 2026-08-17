from memoria_resolutiva.inference_chain import InferenceChain


def main():
    g = InferenceChain(hop_penalty=0.95, max_depth=4)
    g.add("A", "causes", "B", 0.90, "obs_ab")
    g.add("B", "enables", "C", 0.85, "obs_bc")
    g.add("C", "supports", "D", 0.80, "obs_cd")
    g.add("A", "direct", "D", 0.40, "weak_ad")

    for target in ("C", "D"):
        print("target", target)
        for path in g.infer("A", target):
            print(path.nodes, round(path.confidence, 4), [e.provenance for e in path.edges])


if __name__ == "__main__":
    main()
