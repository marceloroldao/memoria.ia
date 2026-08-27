from __future__ import annotations

import itertools
import json

from benchmarks.role_joint_boundary_length_normalized import rows_for_spec
from benchmarks.role_joint_boundary_robustness import long_sequence_spec
from benchmarks.role_permutation_cost_matrix import DOMAINS, assignment_cost
from memoria_resolutiva.role_structural_router_v96 import RoleStructuralRouterV96

BOS = "__bos__"
EOS = "__eos__"


def edge_directional_score(router: RoleStructuralRouterV96, tokens):
    assoc = router.roles.memory.context
    seq = (BOS,) + tuple(tokens) + (EOS,)
    total = 0.0
    pairs = 0
    radius = assoc.radius
    for i, token in enumerate(seq):
        profile = assoc.profiles.get(token)
        if not profile:
            continue
        lo = max(0, i - radius)
        hi = min(len(seq), i + radius + 1)
        for j in range(lo, hi):
            if j == i:
                continue
            pairs += 1
            feature = (j - i, seq[j])
            value = profile.get(feature, 0)
            denom = max(1, assoc.observations.get(token, 0))
            total += value / denom
    return total / max(1, pairs)


def build_edge_router(spec, *, role_top_k, beam_width, max_context_relabels):
    router = RoleStructuralRouterV96(
        role_threshold=0.30,
        role_min_margin=0.02,
        role_top_k=role_top_k,
        beam_width=beam_width,
        max_context_relabels=max_context_relabels,
    )
    # The same sparse ContextAssociator gets explicit trajectory boundaries.
    router.observe([f"{BOS} {sentence} {EOS}" for sentence in spec["observe"]])
    for role_id, anchors in spec["roles"].items():
        router.register_role(role_id, anchors)
    return router


def rows_for_edge_spec(name, spec, *, role_top_k=4, beam_width=256, max_context_relabels=4):
    router = build_edge_router(
        spec,
        role_top_k=role_top_k,
        beam_width=beam_width,
        max_context_relabels=max_context_relabels,
    )
    token_roles = spec["tokens"]
    patterns = [tuple(p) for p in spec["patterns"]]
    pattern_set = set(patterns)
    rows = []
    for perm in itertools.permutations(token_roles.keys()):
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
            "mean_cost": None if total_cost is None else total_cost / len(perm),
            "edge_direction": edge_directional_score(router, perm),
        })
    return rows


def fit(rows):
    usable = [r for r in rows if r["mean_cost"] is not None]
    valid = [r for r in usable if r["valid"]]
    invalid = [r for r in usable if not r["valid"]]
    best = None
    for i in range(0, 5001):
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
            }
    return best


def evaluate(rows, boundary):
    usable = [r for r in rows if r["mean_cost"] is not None]
    tp = tn = fp = fn = 0
    errors = []
    for r in usable:
        joint = r["edge_direction"] - boundary["lambda"] * r["mean_cost"]
        pred = joint > boundary["threshold"]
        if r["valid"] and pred: tp += 1
        elif r["valid"] and not pred: fn += 1
        elif not r["valid"] and pred: fp += 1
        else: tn += 1
        if pred != r["valid"]:
            errors.append({**r, "joint": joint, "predicted_valid": pred})
    return {
        "usable": len(usable), "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "accuracy": (tp + tn) / max(1, len(usable)), "errors": errors,
    }


def main():
    rows4 = [r for name, spec in DOMAINS.items() for r in rows_for_edge_spec(name, spec)]
    rows6 = rows_for_edge_spec(
        "long6", long_sequence_spec(), role_top_k=6, beam_width=4096, max_context_relabels=6
    )
    boundary4 = fit(rows4)
    combined = fit(rows4 + rows6)
    output = {
        "method": "BOS/EOS-augmented signed directional support + mean contradiction cost",
        "fit_4_only": boundary4,
        "train_4": evaluate(rows4, boundary4),
        "held_out_6": evaluate(rows6, boundary4),
        "combined_fit": combined,
        "combined_4": evaluate(rows4, combined),
        "combined_6": evaluate(rows6, combined),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
