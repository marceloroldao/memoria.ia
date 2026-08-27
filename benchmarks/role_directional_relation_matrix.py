from __future__ import annotations

import itertools
import json
from statistics import mean

from benchmarks.role_permutation_cost_matrix import DOMAINS, build_router


def directional_score(router, tokens: tuple[str, ...]) -> float:
    """Measure exact signed-neighborhood support already stored by ContextAssociator.

    This is deliberately a probe, not production policy. For every ordered pair
    within the associator radius, measure how often the destination token was
    observed at that signed offset around the source, normalized by source
    observations. Exact direction matters: (A,+1,B) is distinct from (B,+1,A).
    """
    assoc = router.roles.memory.associator
    radius = assoc.radius
    scores = []
    for i, source in enumerate(tokens):
        profile = assoc.profiles.get(source)
        observations = assoc.observations.get(source, 0)
        if not profile or observations <= 0:
            continue
        lo = max(0, i - radius)
        hi = min(len(tokens), i + radius + 1)
        for j in range(lo, hi):
            if i == j:
                continue
            destination = tokens[j]
            count = profile.get((j - i, destination), 0)
            scores.append(count / observations)
    return mean(scores) if scores else 0.0


def evaluate_domain(name, spec):
    router = build_router(spec)
    token_roles = spec["tokens"]
    patterns = {tuple(p) for p in spec["patterns"]}
    rows = []
    for perm in itertools.permutations(token_roles.keys()):
        roles = tuple(token_roles[token] for token in perm)
        rows.append({
            "tokens": list(perm),
            "roles": list(roles),
            "valid": roles in patterns,
            "directional_score": directional_score(router, perm),
        })

    valid = [row["directional_score"] for row in rows if row["valid"]]
    invalid = [row["directional_score"] for row in rows if not row["valid"]]
    valid_min = min(valid)
    invalid_max = max(invalid)
    return {
        "domain": name,
        "permutations": len(rows),
        "valid_min_directional_score": valid_min,
        "invalid_max_directional_score": invalid_max,
        "separation_margin": valid_min - invalid_max,
        "separable": valid_min > invalid_max,
        "valid_rows": sorted(
            (row for row in rows if row["valid"]),
            key=lambda row: (-row["directional_score"], row["tokens"]),
        ),
        "strongest_invalid": sorted(
            (row for row in rows if not row["valid"]),
            key=lambda row: (-row["directional_score"], row["tokens"]),
        )[:5],
    }


def main():
    domains = [evaluate_domain(name, spec) for name, spec in DOMAINS.items()]
    global_valid_min = min(row["valid_min_directional_score"] for row in domains)
    global_invalid_max = max(row["invalid_max_directional_score"] for row in domains)
    print(json.dumps({
        "domains": domains,
        "global_valid_min_directional_score": global_valid_min,
        "global_invalid_max_directional_score": global_invalid_max,
        "global_separation_margin": global_valid_min - global_invalid_max,
        "globally_separable": global_valid_min > global_invalid_max,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
