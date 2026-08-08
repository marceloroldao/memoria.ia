from memoria_resolutiva.multipath_fusion import EvidencePath, fuse_paths


def main():
    independent = [
        EvidencePath("A=>D", 0.72, frozenset({"root_ab", "root_bd"}), "path_ABD"),
        EvidencePath("A=>D", 0.68, frozenset({"root_ac", "root_cd"}), "path_ACD"),
    ]
    dependent = independent + [
        EvidencePath("A=>D", 0.75, frozenset({"root_ab", "root_be", "root_ed"}), "path_ABED"),
    ]

    print("independent", fuse_paths(independent))
    print("with_dependent_copy", fuse_paths(dependent))


if __name__ == "__main__":
    main()
