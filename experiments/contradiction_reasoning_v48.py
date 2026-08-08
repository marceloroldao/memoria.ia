from memoria_resolutiva.contradiction_reasoning import Argument, decide_conflict


def main():
    balanced = [
        Argument("D", True, 0.78, frozenset({"obs_A"})),
        Argument("D", False, 0.75, frozenset({"obs_B"})),
    ]
    print("balanced", decide_conflict(balanced, "D"))

    strong_support = balanced + [
        Argument("D", True, 0.72, frozenset({"obs_C"})),
    ]
    print("independent support", decide_conflict(strong_support, "D"))

    duplicated_root = balanced + [
        Argument("D", True, 0.76, frozenset({"obs_A", "derived_X"})),
        Argument("D", True, 0.74, frozenset({"derived_X"})),
    ]
    print("dependent support", decide_conflict(duplicated_root, "D"))


if __name__ == "__main__":
    main()
