from memoria_resolutiva.evidence_independence import EvidenceItem, IndependentEvidenceResolver


def run_echo_case():
    r = IndependentEvidenceResolver(min_margin=0.15)
    # Ten sources repeat the same origin claiming X.
    for i in range(10):
        r.observe(EvidenceItem("claim", "x", f"copy_{i}", "origin_x", 1.0))
    # Two genuinely independent origins claim Y.
    r.observe(EvidenceItem("claim", "y", "source_y1", "origin_y1", 1.0))
    r.observe(EvidenceItem("claim", "y", "source_y2", "origin_y2", 1.0))
    return r.resolve("claim")


def run_independent_majority_case():
    r = IndependentEvidenceResolver(min_margin=0.15)
    r.observe(EvidenceItem("claim", "x", "a", "origin_a", 1.0))
    r.observe(EvidenceItem("claim", "x", "b", "origin_b", 1.0))
    r.observe(EvidenceItem("claim", "x", "c", "origin_c", 1.0))
    r.observe(EvidenceItem("claim", "y", "d", "origin_d", 1.0))
    return r.resolve("claim")


if __name__ == "__main__":
    print("echo_case", run_echo_case())
    print("independent_majority", run_independent_majority_case())
