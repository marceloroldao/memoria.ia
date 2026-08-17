from memoria_resolutiva.source_reliability import SourceReliabilityMemory


def main():
    memory = SourceReliabilityMemory()

    # Historical outcomes learned online. These are deliberately synthetic.
    for _ in range(92):
        memory.confirm("fonte_a")
    for _ in range(8):
        memory.contradict("fonte_a")

    for _ in range(55):
        memory.confirm("fonte_b")
    for _ in range(45):
        memory.contradict("fonte_b")

    print("fonte_a", memory.snapshot()["fonte_a"])
    print("fonte_b", memory.snapshot()["fonte_b"])

    # New disagreement: reliability is learned from prior resolved claims.
    claim_a = memory.reliability("fonte_a")
    claim_b = memory.reliability("fonte_b")
    total = claim_a + claim_b
    print("new_conflict_scores", {"A": claim_a, "B": claim_b})
    print("normalized_support", {"A": claim_a / total, "B": claim_b / total})


if __name__ == "__main__":
    main()
