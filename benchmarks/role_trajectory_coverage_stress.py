from __future__ import annotations

import itertools
import json

from benchmarks.role_joint_boundary_trajectory_edges import BOS, EOS, build_edge_router
from benchmarks.role_trajectory_direction_stress import (
    contradictory_spec,
    insertion_deletion_rows,
    single_anchor_spec,
    spec3,
    spec5,
)


def trajectory_coverage(router, tokens):
    """Fraction of expected signed local relations that are actually present.

    Unlike edge_directional_score this is deliberately binary: relation strength
    is not allowed to dominate merely because an anchor/token was observed more
    often. Every expected signed edge within the ContextAssociator radius counts
    once, including BOS/EOS boundary edges.
    """
    assoc = router.roles.memory.associator
    seq = (BOS,) + tuple(tokens) + (EOS,)
    supported = 0
    expected = 0
    radius = assoc.radius
    for i, token in enumerate(seq):
        profile = assoc.profiles.get(token)
        lo = max(0, i - radius)
        hi = min(len(seq), i + radius + 1)
        for j in range(lo, hi):
            if j == i:
                continue
            expected += 1
            if profile and profile.get((j - i, seq[j]), 0) > 0:
                supported += 1
    return supported / max(1, expected)


def calibration_rows(router, spec):
    # A structural calibrator still needs at least two lexical examples per role
    # to claim any hold-out generalization. Otherwise it must fail closed.
    if any(len(anchors) < 2 for anchors in spec["roles"].values()):
        return []
    patterns = [tuple(p) for p in spec["patterns"]]
    pattern_set = set(patterns)
    role_by_anchor = {
        anchor: role
        for role, anchors in spec["roles"].items()
        for anchor in anchors
    }
    rows = []
    max_anchors = max(len(v) for v in spec["roles"].values())
    seen = set()
    for pattern in patterns:
        for shift in range(max_anchors):
            seq = tuple(spec["roles"][role][shift % len(spec["roles"][role])] for role in pattern)
            for perm in itertools.permutations(seq):
                if perm in seen:
                    continue
                seen.add(perm)
                roles = tuple(role_by_anchor[t] for t in perm)
                rows.append({
                    "tokens": list(perm),
                    "valid": roles in pattern_set,
                    "coverage": trajectory_coverage(router, perm),
                })
    return rows


def fit(rows):
    valid = [r for r in rows if r["valid"]]
    invalid = [r for r in rows if not r["valid"]]
    if not valid or not invalid:
        return {"separable": False, "reason": "insufficient calibration classes"}
    vmin = min(r["coverage"] for r in valid)
    imax = max(r["coverage"] for r in invalid)
    margin = vmin - imax
    return {
        "threshold": (vmin + imax) / 2.0,
        "margin": margin,
        "separable": margin > 0.0,
    }


def evaluate(rows, boundary, expected_length):
    if not boundary.get("separable"):
        return {"fail_closed": True, "usable": len(rows), "accepted": 0}
    tp = tn = fp = fn = 0
    errors = []
    for row in rows:
        # Length is part of trajectory topology: a learned N-node pattern cannot
        # be satisfied by N-1 or N+1 nodes even if surviving local edges are strong.
        pred = len(row["tokens"]) == expected_length and row["coverage"] > boundary["threshold"]
        if row["valid"] and pred:
            tp += 1
        elif row["valid"]:
            fn += 1
        elif pred:
            fp += 1
        else:
            tn += 1
        if pred != row["valid"]:
            errors.append({**row, "predicted_valid": pred})
    return {
        "fail_closed": False,
        "usable": len(rows),
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "accuracy": (tp + tn) / max(1, len(rows)),
        "errors": errors,
    }


def novel_permutations(router, spec):
    patterns = [tuple(p) for p in spec["patterns"]]
    pattern_set = set(patterns)
    roles = spec["tokens"]
    rows = []
    for perm in itertools.permutations(roles.keys()):
        ground = tuple(roles[t] for t in perm)
        rows.append({
            "tokens": list(perm),
            "valid": ground in pattern_set,
            "coverage": trajectory_coverage(router, perm),
        })
    return rows


def altered_rows(router, spec):
    # Reuse the same generated deformation set, but recompute the experimental metric.
    rows = insertion_deletion_rows(router, spec)
    return [
        {
            "kind": row["kind"],
            "tokens": row["tokens"],
            "valid": row["valid"],
            "coverage": trajectory_coverage(router, tuple(row["tokens"])),
        }
        for row in rows
    ]


def run(name, spec):
    n = len(next(iter(spec["patterns"])))
    router = build_edge_router(
        spec,
        role_top_k=max(4, n),
        beam_width=4096 if n >= 5 else 256,
        max_context_relabels=n,
    )
    cal = calibration_rows(router, spec)
    boundary = fit(cal)
    permutations = evaluate(novel_permutations(router, spec), boundary, n)
    alterations = evaluate(altered_rows(router, spec), boundary, n)
    return {
        "name": name,
        "length": n,
        "calibration_examples": len(cal),
        "boundary": boundary,
        "permutations": permutations,
        "insert_delete": alterations,
    }


def main():
    cases = [
        run("length3", spec3()),
        run("length5", spec5()),
        run("contradictory_length3", contradictory_spec()),
        run("single_anchor_fail_closed", single_anchor_spec()),
    ]
    print(json.dumps({
        "method": "binary signed trajectory coverage + explicit learned trajectory length",
        "lexical_contradiction_cost_used": False,
        "cases": cases,
        "summary": {
            "length3_perfect": cases[0]["permutations"].get("accuracy") == 1.0,
            "length5_perfect": cases[1]["permutations"].get("accuracy") == 1.0,
            "length3_deformations_rejected": cases[0]["insert_delete"].get("fp", 0) == 0,
            "length5_deformations_rejected": cases[1]["insert_delete"].get("fp", 0) == 0,
            "contradictory_perfect": cases[2]["permutations"].get("accuracy") == 1.0,
            "single_anchor_fail_closed": cases[3]["permutations"].get("fail_closed", False),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
