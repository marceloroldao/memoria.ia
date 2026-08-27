from __future__ import annotations

import json

from benchmarks.role_joint_cost_direction_boundary import rows_for_domain
from benchmarks.role_permutation_cost_matrix import DOMAINS


def score(row, lam):
    return row["direction"] - lam * row["cost"]


def best_linear_boundary(rows):
    usable = [r for r in rows if r["cost"] is not None]
    valid = [r for r in usable if r["valid"]]
    invalid = [r for r in usable if not r["valid"]]
    candidates = {x / 1000.0 for x in range(0, 5001)}
    best = None
    for lam in candidates:
        vmin = min(score(r, lam) for r in valid)
        imax = max(score(r, lam) for r in invalid)
        margin = vmin - imax
        if best is None or margin > best["margin"]:
            best = {
                "lambda": lam,
                "threshold": (vmin + imax) / 2.0,
                "margin": margin,
            }
    return best


def evaluate(rows, boundary):
    usable = [r for r in rows if r["cost"] is not None]
    predictions = []
    for r in usable:
        s = score(r, boundary["lambda"])
        pred = s > boundary["threshold"]
        predictions.append((r, pred, s))
    tp = sum(r["valid"] and pred for r, pred, _ in predictions)
    fn = sum(r["valid"] and not pred for r, pred, _ in predictions)
    fp = sum((not r["valid"]) and pred for r, pred, _ in predictions)
    tn = sum((not r["valid"]) and not pred for r, pred, _ in predictions)
    return {
        "usable": len(usable),
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "valid_recall": tp / max(1, tp + fn),
        "invalid_rejection": tn / max(1, tn + fp),
        "accuracy": (tp + tn) / max(1, len(usable)),
        "errors": [
            {
                "domain": r["domain"],
                "tokens": r["tokens"],
                "valid": r["valid"],
                "cost": r["cost"],
                "direction": r["direction"],
                "joint_score": s,
                "predicted_valid": pred,
            }
            for r, pred, s in predictions
            if pred != r["valid"]
        ],
    }


def main():
    by_domain = {name: rows_for_domain(name, spec) for name, spec in DOMAINS.items()}
    folds = []
    for held_out in by_domain:
        train = [r for name, rows in by_domain.items() if name != held_out for r in rows]
        test = by_domain[held_out]
        boundary = best_linear_boundary(train)
        folds.append({
            "held_out": held_out,
            "train_boundary": boundary,
            "train": evaluate(train, boundary),
            "test": evaluate(test, boundary),
        })
    print(json.dumps({
        "method": "leave-one-domain-out; score = direction - lambda * cost",
        "folds": folds,
        "all_held_out_perfect": all(f["test"]["accuracy"] == 1.0 for f in folds),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
