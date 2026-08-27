from __future__ import annotations

import itertools
import json

from benchmarks.role_directional_relation_matrix import directional_score
from benchmarks.role_joint_boundary_robustness import long_sequence_spec
from benchmarks.role_permutation_cost_matrix import DOMAINS, assignment_cost, build_router
from memoria_resolutiva.role_structural_router_v96 import RoleStructuralRouterV96


def rows_for_spec(name, spec, *, role_top_k=4, beam_width=256, max_context_relabels=4):
    router = RoleStructuralRouterV96(
        role_threshold=0.30,
        role_min_margin=0.02,
        role_top_k=role_top_k,
        beam_width=beam_width,
        max_context_relabels=max_context_relabels,
    )
    router.observe(spec["observe"])
    for role_id, anchors in spec["roles"].items():
        router.register_role(role_id, anchors)
    tokens = list(spec["tokens"].keys())
    token_roles = spec["tokens"]
    patterns = [tuple(p) for p in spec["patterns"]]
    pattern_set = set(patterns)
    rows = []
    for perm in itertools.permutations(tokens):
        ground = tuple(token_roles[t] for t in perm)
        fits = []
        for pattern in patterns:
            measured = assignment_cost(router, perm, pattern)
            if measured is not None:
                fits.append(measured["cost"])
        total_cost = min(fits) if fits else None
        rows.append({
            "domain": name,
            "length": len(perm),
            "tokens": list(perm),
            "valid": ground in pattern_set,
            "total_cost": total_cost,
            "mean_cost": None if total_cost is None else total_cost / len(perm),
            "direction": directional_score(router, perm),
        })
    return rows


def fit_boundary(rows, cost_field):
    usable = [r for r in rows if r[cost_field] is not None]
    valid = [r for r in usable if r["valid"]]
    invalid = [r for r in usable if not r["valid"]]
    best = None
    for i in range(0, 5001):
        lam = i / 1000.0
        vs = [r["direction"] - lam * r[cost_field] for r in valid]
        ins = [r["direction"] - lam * r[cost_field] for r in invalid]
        margin = min(vs) - max(ins)
        if best is None or margin > best["margin"]:
            best = {
                "lambda": lam,
                "threshold": (min(vs) + max(ins)) / 2.0,
                "margin": margin,
                "separable": margin > 0.0,
            }
    return best


def evaluate(rows, boundary, cost_field):
    usable = [r for r in rows if r[cost_field] is not None]
    errors = []
    tp = tn = fp = fn = 0
    for r in usable:
        joint = r["direction"] - boundary["lambda"] * r[cost_field]
        pred = joint > boundary["threshold"]
        if r["valid"] and pred: tp += 1
        elif r["valid"] and not pred: fn += 1
        elif not r["valid"] and pred: fp += 1
        else: tn += 1
        if pred != r["valid"]:
            errors.append({
                "domain": r["domain"], "length": r["length"], "tokens": r["tokens"],
                "valid": r["valid"], cost_field: r[cost_field], "direction": r["direction"],
                "joint": joint, "predicted_valid": pred,
            })
    return {
        "usable": len(usable), "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "accuracy": (tp + tn) / max(1, len(usable)), "errors": errors,
    }


def main():
    rows4 = [r for name, spec in DOMAINS.items() for r in rows_for_spec(name, spec)]
    spec6 = long_sequence_spec()
    rows6 = rows_for_spec("long6", spec6, role_top_k=6, beam_width=4096, max_context_relabels=6)

    total_boundary = fit_boundary(rows4, "total_cost")
    mean_boundary = fit_boundary(rows4, "mean_cost")

    output = {
        "training_4_role": {
            "total_cost_boundary": total_boundary,
            "mean_cost_boundary": mean_boundary,
            "total_eval": evaluate(rows4, total_boundary, "total_cost"),
            "mean_eval": evaluate(rows4, mean_boundary, "mean_cost"),
        },
        "held_out_6_role": {
            "using_total_cost_boundary": evaluate(rows6, total_boundary, "total_cost"),
            "using_mean_cost_boundary": evaluate(rows6, mean_boundary, "mean_cost"),
        },
        "joint_fit_4_and_6": {
            "total_cost": fit_boundary(rows4 + rows6, "total_cost"),
            "mean_cost": fit_boundary(rows4 + rows6, "mean_cost"),
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
