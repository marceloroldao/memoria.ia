from __future__ import annotations

import json

from benchmarks.role_joint_boundary_robustness import long_sequence_spec
from benchmarks.role_joint_boundary_unseen_domains import UNSEEN
from benchmarks.role_joint_self_calibration import (
    calibration_rows,
    evaluate,
    novel_rows,
)
from benchmarks.role_joint_boundary_trajectory_edges import build_edge_router
from benchmarks.role_permutation_cost_matrix import DOMAINS


def fit_direction_only(rows):
    valid = [r for r in rows if r["valid"]]
    invalid = [r for r in rows if not r["valid"]]
    if not valid or not invalid:
        return {"separable": False, "reason": "insufficient calibration classes"}
    vmin = min(r["edge_direction"] for r in valid)
    imax = max(r["edge_direction"] for r in invalid)
    margin = vmin - imax
    return {
        "lambda": 0.0,
        "threshold": (vmin + imax) / 2.0,
        "margin": margin,
        "separable": margin > 0.0,
    }


def fit_joint(rows):
    valid = [r for r in rows if r["valid"]]
    invalid = [r for r in rows if not r["valid"]]
    if not valid or not invalid:
        return {"separable": False, "reason": "insufficient calibration classes"}
    best = None
    # Keep the scan bounded; an optimum at the upper edge is reported rather than
    # silently interpreted as a stable coefficient.
    for i in range(0, 10001):
        lam = i / 1000.0
        vs = [r["edge_direction"] - lam * r["mean_cost"] for r in valid]
        ins = [r["edge_direction"] - lam * r["mean_cost"] for r in invalid]
        margin = min(vs) - max(ins)
        if best is None or margin > best["margin"]:
            best = {
                "lambda": lam,
                "threshold": (min(vs) + max(ins)) / 2.0,
                "margin": margin,
                "separable": margin > 0.0,
                "hit_upper_scan_edge": lam == 10.0,
            }
    return best


def run_domain(name, spec):
    n = len(next(iter(spec["patterns"])))
    router = build_edge_router(
        spec,
        role_top_k=max(4, n),
        beam_width=4096 if n >= 6 else 256,
        max_context_relabels=n,
    )
    calibration = calibration_rows(router, spec)
    test = novel_rows(router, spec)
    direction = fit_direction_only(calibration)
    joint = fit_joint(calibration)
    return {
        "domain": name,
        "length": n,
        "calibration_examples": len(calibration),
        "direction_only": {
            "boundary": direction,
            "novel": evaluate(test, direction),
        },
        "joint": {
            "boundary": joint,
            "novel": evaluate(test, joint),
        },
    }


def main():
    groups = []
    for group, specs in (
        ("original", DOMAINS),
        ("unseen_4_role", UNSEEN),
        ("long6", {"long6": long_sequence_spec()}),
    ):
        results = [run_domain(name, spec) for name, spec in specs.items()]
        groups.append({
            "group": group,
            "results": results,
            "direction_all_perfect": all(
                r["direction_only"]["boundary"].get("separable", False)
                and r["direction_only"]["novel"].get("accuracy") == 1.0
                for r in results
            ),
            "joint_all_perfect": all(
                r["joint"]["boundary"].get("separable", False)
                and r["joint"]["novel"].get("accuracy") == 1.0
                for r in results
            ),
        })
    print(json.dumps({
        "question": "Does BOS/EOS signed trajectory support make contradiction cost unnecessary?",
        "calibration": "per-router leave-one-anchor-out; no novel test token used",
        "groups": groups,
        "direction_only_wins_everywhere": all(g["direction_all_perfect"] for g in groups),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
