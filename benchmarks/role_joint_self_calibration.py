from __future__ import annotations

import itertools
import json

from benchmarks.role_joint_boundary_robustness import long_sequence_spec
from benchmarks.role_joint_boundary_trajectory_edges import edge_directional_score, build_edge_router
from benchmarks.role_joint_boundary_unseen_domains import UNSEEN
from benchmarks.role_permutation_cost_matrix import DOMAINS, assignment_cost


def point(router, tokens, patterns):
    """Normal query-side point using the real role candidate policy."""
    fits = []
    for pattern in patterns:
        measured = assignment_cost(router, tokens, pattern)
        if measured is not None:
            fits.append(measured["cost"])
    if not fits:
        return None
    total_cost = min(fits)
    return {
        "mean_cost": total_cost / len(tokens),
        "edge_direction": edge_directional_score(router, tuple(tokens)),
    }


def contextual_assignment_cost(router, tokens, pattern):
    """Calibration-only contradiction cost from raw contextual rankings.

    Registered anchors remain exact during normal inference. For counterfactual
    calibration we deliberately bypass that lexical shortcut and ask the sparse
    contextual memory how strongly each anchor supports every registered role.
    This yields finite negative examples without weakening production semantics.
    """
    role_count = max(1, len(router.roles._concepts))
    total = 0.0
    for token, target_role in zip(tokens, pattern):
        ranked = router.roles.memory.rank_registered(token, None, top_k=role_count)
        if ranked is None:
            return None
        ranked = [(role, float(score)) for role, score in ranked]
        if not ranked:
            return None
        top_score = ranked[0][1]
        selected = next((score for role, score in ranked if role == target_role), None)
        if selected is None:
            return None
        total += max(0.0, top_score - selected)
    return total


def calibration_point(router, tokens, patterns):
    fits = []
    for pattern in patterns:
        cost = contextual_assignment_cost(router, tokens, pattern)
        if cost is not None:
            fits.append(cost)
    if not fits:
        return None
    return {
        "mean_cost": min(fits) / len(tokens),
        "edge_direction": edge_directional_score(router, tuple(tokens)),
    }


def representative_anchor_tuples(spec):
    """Bounded deterministic positives built only from registered anchors."""
    roles = spec["roles"]
    patterns = [tuple(p) for p in spec["patterns"]]
    max_anchors = max(len(roles[role]) for pattern in patterns for role in pattern)
    rows = []
    seen = set()
    for pattern in patterns:
        for shift in range(max_anchors):
            tokens = tuple(roles[role][shift % len(roles[role])] for role in pattern)
            if tokens not in seen:
                seen.add(tokens)
                rows.append((tokens, pattern))
    return rows


def calibration_rows(router, spec):
    patterns = [tuple(p) for p in spec["patterns"]]
    pattern_set = set(patterns)
    role_by_anchor = {
        anchor: role
        for role, anchors in spec["roles"].items()
        for anchor in anchors
    }
    rows = []
    for positive_tokens, _pattern in representative_anchor_tuples(spec):
        for perm in itertools.permutations(positive_tokens):
            roles = tuple(role_by_anchor[token] for token in perm)
            measured = calibration_point(router, perm, patterns)
            if measured is None:
                continue
            rows.append({
                "tokens": list(perm),
                "valid": roles in pattern_set,
                **measured,
            })
    dedup = {}
    for row in rows:
        dedup[tuple(row["tokens"])] = row
    return list(dedup.values())


def fit_boundary(rows):
    valid = [r for r in rows if r["valid"]]
    invalid = [r for r in rows if not r["valid"]]
    if not valid or not invalid:
        return {"separable": False, "reason": "insufficient calibration classes"}
    best = None
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
            }
    return best


def novel_rows(router, spec):
    token_roles = spec["tokens"]
    patterns = [tuple(p) for p in spec["patterns"]]
    pattern_set = set(patterns)
    rows = []
    for perm in itertools.permutations(token_roles.keys()):
        roles = tuple(token_roles[token] for token in perm)
        measured = point(router, perm, patterns)
        if measured is None:
            continue
        rows.append({
            "tokens": list(perm),
            "valid": roles in pattern_set,
            **measured,
        })
    return rows


def evaluate(rows, boundary):
    if not boundary.get("separable"):
        return {
            "fail_closed": True,
            "usable": len(rows),
            "accepted": 0,
            "accuracy_if_all_rejected": sum(not r["valid"] for r in rows) / max(1, len(rows)),
        }
    tp = tn = fp = fn = 0
    errors = []
    for row in rows:
        joint = row["edge_direction"] - boundary["lambda"] * row["mean_cost"]
        predicted = joint > boundary["threshold"]
        if row["valid"] and predicted:
            tp += 1
        elif row["valid"]:
            fn += 1
        elif predicted:
            fp += 1
        else:
            tn += 1
        if predicted != row["valid"]:
            errors.append({**row, "joint_score": joint, "predicted_valid": predicted})
    return {
        "fail_closed": False,
        "usable": len(rows),
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "valid_recall": tp / max(1, tp + fn),
        "invalid_rejection": tn / max(1, tn + fp),
        "accuracy": (tp + tn) / max(1, len(rows)),
        "errors": errors,
    }


def run_domain(name, spec, *, role_top_k=None, beam_width=None, max_context_relabels=None):
    n = len(next(iter(spec["patterns"])))
    router = build_edge_router(
        spec,
        role_top_k=role_top_k or max(4, n),
        beam_width=beam_width or (4096 if n >= 6 else 256),
        max_context_relabels=max_context_relabels or n,
    )
    calibration = calibration_rows(router, spec)
    boundary = fit_boundary(calibration)
    test = novel_rows(router, spec)
    return {
        "domain": name,
        "sequence_length": n,
        "calibration_examples": len(calibration),
        "calibration_valid": sum(r["valid"] for r in calibration),
        "calibration_invalid": sum(not r["valid"] for r in calibration),
        "boundary": boundary,
        "novel_test": evaluate(test, boundary),
    }


def main():
    suites = []
    for group, specs in (
        ("original", DOMAINS),
        ("unseen_domains", UNSEEN),
        ("long_sequence", {"long6": long_sequence_spec()}),
    ):
        results = [run_domain(name, spec) for name, spec in specs.items()]
        suites.append({
            "group": group,
            "results": results,
            "all_calibrated": all(r["boundary"].get("separable", False) for r in results),
            "all_novel_perfect": all(r["novel_test"].get("accuracy") == 1.0 for r in results),
        })

    print(json.dumps({
        "method": "per-router deterministic self-calibration from registered anchors; counterfactual costs use raw sparse contextual rankings",
        "normal_inference_keeps_exact_anchor_semantics": True,
        "uses_novel_test_tokens_for_calibration": False,
        "suites": suites,
        "all_suites_perfect": all(s["all_calibrated"] and s["all_novel_perfect"] for s in suites),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
