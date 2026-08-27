from __future__ import annotations

import itertools
import json

from benchmarks.role_directional_relation_matrix import directional_score
from benchmarks.role_permutation_cost_matrix import DOMAINS, assignment_cost, build_router


def rows_for_domain(name, spec):
    router = build_router(spec)
    token_roles = spec["tokens"]
    patterns = [tuple(p) for p in spec["patterns"]]
    rows = []
    for perm in itertools.permutations(token_roles.keys()):
        roles = tuple(token_roles[token] for token in perm)
        fits = []
        for pattern in patterns:
            measured = assignment_cost(router, perm, pattern)
            if measured is not None:
                fits.append(measured["cost"])
        rows.append({
            "domain": name,
            "tokens": list(perm),
            "valid": roles in set(patterns),
            "cost": min(fits) if fits else None,
            "direction": directional_score(router, perm),
        })
    return rows


def linear_boundary(rows):
    # score = direction - lambda * cost. Exhaustively scan breakpoints and a
    # dense deterministic grid; report a boundary only when every valid score is
    # strictly above every invalid score.
    valid = [r for r in rows if r["valid"] and r["cost"] is not None]
    invalid = [r for r in rows if not r["valid"] and r["cost"] is not None]
    candidates = {0.0}
    for v in valid:
        for i in invalid:
            dc = v["cost"] - i["cost"]
            if abs(dc) > 1e-15:
                lam = (v["direction"] - i["direction"]) / dc
                if 0.0 <= lam <= 100.0:
                    candidates.add(lam)
                    candidates.add(max(0.0, lam - 1e-9))
                    candidates.add(min(100.0, lam + 1e-9))
    candidates.update(x / 100.0 for x in range(0, 10001))
    best = None
    for lam in sorted(candidates):
        valid_scores = [r["direction"] - lam * r["cost"] for r in valid]
        invalid_scores = [r["direction"] - lam * r["cost"] for r in invalid]
        margin = min(valid_scores) - max(invalid_scores)
        if best is None or margin > best["margin"]:
            threshold = (min(valid_scores) + max(invalid_scores)) / 2.0
            best = {"lambda": lam, "margin": margin, "threshold": threshold}
    return {**best, "separable": best["margin"] > 0.0}


def rectangular_boundary(rows):
    valid = [r for r in rows if r["valid"] and r["cost"] is not None]
    invalid = [r for r in rows if not r["valid"] and r["cost"] is not None]
    cost_candidates = sorted({r["cost"] for r in rows if r["cost"] is not None})
    dir_candidates = sorted({r["direction"] for r in rows})
    solutions = []
    for c in cost_candidates:
        for d in dir_candidates:
            def accept(r):
                return r["cost"] <= c and r["direction"] >= d
            if all(accept(r) for r in valid) and not any(accept(r) for r in invalid):
                solutions.append({"max_cost": c, "min_direction": d})
    return {"separable": bool(solutions), "solutions": solutions[:20]}


def lexicographic_boundary(rows):
    # Lower cost first; direction is only a tie-breaker. This checks whether any
    # invalid point is lexicographically at least as plausible as the worst valid.
    def key(r):
        return (r["cost"], -r["direction"])
    valid = sorted((r for r in rows if r["valid"] and r["cost"] is not None), key=key)
    invalid = sorted((r for r in rows if not r["valid"] and r["cost"] is not None), key=key)
    worst_valid = max(valid, key=key)
    best_invalid = min(invalid, key=key)
    return {
        "separable": key(worst_valid) < key(best_invalid),
        "worst_valid": {"cost": worst_valid["cost"], "direction": worst_valid["direction"], "domain": worst_valid["domain"], "tokens": worst_valid["tokens"]},
        "best_invalid": {"cost": best_invalid["cost"], "direction": best_invalid["direction"], "domain": best_invalid["domain"], "tokens": best_invalid["tokens"]},
    }


def pareto_collisions(rows):
    valid = [r for r in rows if r["valid"] and r["cost"] is not None]
    invalid = [r for r in rows if not r["valid"] and r["cost"] is not None]
    collisions = []
    for i in invalid:
        dominated_valid = [v for v in valid if i["cost"] <= v["cost"] and i["direction"] >= v["direction"]]
        if dominated_valid:
            collisions.append({
                "invalid": {"domain": i["domain"], "tokens": i["tokens"], "cost": i["cost"], "direction": i["direction"]},
                "valids_dominated": [
                    {"domain": v["domain"], "tokens": v["tokens"], "cost": v["cost"], "direction": v["direction"]}
                    for v in dominated_valid
                ],
            })
    return collisions


def main():
    rows = []
    for name, spec in DOMAINS.items():
        rows.extend(rows_for_domain(name, spec))
    output = {
        "points": len(rows),
        "valid": sum(r["valid"] for r in rows),
        "invalid": sum(not r["valid"] for r in rows),
        "linear": linear_boundary(rows),
        "rectangular": rectangular_boundary(rows),
        "lexicographic_cost_then_direction": lexicographic_boundary(rows),
        "pareto_invalid_dominates_valid": pareto_collisions(rows),
        "rows": rows,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
