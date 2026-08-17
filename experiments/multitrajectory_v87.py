from memoria_resolutiva.multitrajectory import MultiTrajectoryMemory


def main():
    m = MultiTrajectoryMemory()
    concepts = 1000
    routes_per_concept = 8
    for i in range(concepts):
        kid = f"k{i}"
        payload = {"concept": i, "facts": tuple(range(16))}
        for r in range(routes_per_concept):
            modality = ("vision", "language", "audio", "motor")[r % 4]
            scope = "private" if r < 4 else "collective"
            m.store(
                kid,
                payload,
                (scope, modality, f"route-{r}", kid),
                modality=modality,
                provenance=f"agent-{r % 3}",
            )
    print({
        "concepts": concepts,
        "routes": m.route_count,
        "payload_nodes": m.knowledge_count,
        "naive_payload_copies": concepts * routes_per_concept,
        "structural_duplication_avoided": m.duplication_ratio(),
    })


if __name__ == "__main__":
    main()
