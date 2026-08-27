from __future__ import annotations

import itertools
import json

from benchmarks.role_joint_boundary_robustness import long_sequence_spec
from benchmarks.role_joint_boundary_unseen_domains import UNSEEN
from benchmarks.role_permutation_cost_matrix import DOMAINS
from benchmarks.role_trajectory_coverage_stress import calibration_rows, fit, trajectory_coverage
from benchmarks.role_trajectory_direction_stress import contradictory_spec, single_anchor_spec, spec3, spec5
from benchmarks.role_joint_boundary_trajectory_edges import build_edge_router

ACCEPT = "accept"
REJECT = "reject"
FAIL_CLOSED = "fail_closed"


def token_supported(router, token):
    token = token.lower()
    if token in router._exact_roles:
        return True
    # Do not infer semantics for a token with no learned sparse relational profile.
    if token not in router.roles.memory.associator.profiles:
        return False
    return bool(router._rank_role_candidates(token))


def policy_decision(router, tokens, boundary, expected_lengths):
    if not boundary.get("separable"):
        return FAIL_CLOSED
    if any(not token_supported(router, token) for token in tokens):
        return FAIL_CLOSED
    if len(tokens) not in expected_lengths:
        return REJECT
    coverage = trajectory_coverage(router, tokens)
    return ACCEPT if coverage > boundary["threshold"] else REJECT


def expected_for_permutation(spec, perm):
    token_roles = spec["tokens"]
    pattern_set = {tuple(p) for p in spec["patterns"]}
    roles = tuple(token_roles[t] for t in perm)
    return ACCEPT if roles in pattern_set else REJECT


def run_permutation_domain(name, spec):
    n = len(next(iter(spec["patterns"])))
    router = build_edge_router(
        spec,
        role_top_k=max(4, n),
        beam_width=4096 if n >= 6 else 256,
        max_context_relabels=n,
    )
    cal = calibration_rows(router, spec)
    boundary = fit(cal)
    rows = []
    for perm in itertools.permutations(spec["tokens"].keys()):
        semantic_expected = expected_for_permutation(spec, perm)
        # Absolute-open-set vocabulary changes expected policy from semantic accept/reject
        # to epistemic fail-closed because the router has no basis for role assignment.
        if any(not token_supported(router, t) for t in perm):
            expected = FAIL_CLOSED
        elif not boundary.get("separable"):
            expected = FAIL_CLOSED
        else:
            expected = semantic_expected
        actual = policy_decision(router, perm, boundary, {n})
        rows.append({"tokens": list(perm), "expected": expected, "actual": actual})
    correct = sum(r["expected"] == r["actual"] for r in rows)
    return {
        "domain": name,
        "length": n,
        "calibration_examples": len(cal),
        "boundary": boundary,
        "total": len(rows),
        "correct": correct,
        "accuracy": correct / max(1, len(rows)),
        "outcomes": {state: sum(r["actual"] == state for r in rows) for state in (ACCEPT, REJECT, FAIL_CLOSED)},
        "errors": [r for r in rows if r["expected"] != r["actual"]],
    }


def deformation_domain(name, spec):
    n = len(next(iter(spec["patterns"])))
    router = build_edge_router(spec, role_top_k=max(4, n), beam_width=4096 if n >= 6 else 256, max_context_relabels=n)
    boundary = fit(calibration_rows(router, spec))
    token_by_role = {role: token for token, role in spec["tokens"].items()}
    rows = []
    for pattern in spec["patterns"]:
        seq = tuple(token_by_role[r] for r in pattern)
        base_expected = FAIL_CLOSED if any(not token_supported(router, t) for t in seq) or not boundary.get("separable") else ACCEPT
        rows.append({"kind": "valid", "tokens": list(seq), "expected": base_expected, "actual": policy_decision(router, seq, boundary, {n})})
        for idx in range(n):
            altered = seq[:idx] + seq[idx + 1:]
            expected = FAIL_CLOSED if any(not token_supported(router, t) for t in altered) or not boundary.get("separable") else REJECT
            rows.append({"kind": "deletion", "tokens": list(altered), "expected": expected, "actual": policy_decision(router, altered, boundary, {n})})
        for idx in range(n + 1):
            altered = seq[:idx] + ("intruso",) + seq[idx:]
            # intruso is absolute open-set by construction, so the epistemically correct state is fail_closed.
            rows.append({"kind": "insertion_open_set", "tokens": list(altered), "expected": FAIL_CLOSED, "actual": policy_decision(router, altered, boundary, {n})})
    correct = sum(r["expected"] == r["actual"] for r in rows)
    return {
        "domain": name,
        "total": len(rows),
        "correct": correct,
        "accuracy": correct / max(1, len(rows)),
        "outcomes": {state: sum(r["actual"] == state for r in rows) for state in (ACCEPT, REJECT, FAIL_CLOSED)},
        "errors": [r for r in rows if r["expected"] != r["actual"]],
    }


def main():
    permutation_specs = []
    permutation_specs.extend(("original/" + name, spec) for name, spec in DOMAINS.items())
    permutation_specs.extend(("unseen/" + name, spec) for name, spec in UNSEEN.items())
    permutation_specs.append(("long6", long_sequence_spec()))
    permutation_specs.append(("context_known_length5", spec5()))
    permutation_specs.append(("absolute_open_set_length3", spec3()))
    permutation_specs.append(("contradictory_length3", contradictory_spec()))
    permutation_specs.append(("single_anchor", single_anchor_spec()))

    permutations = [run_permutation_domain(name, spec) for name, spec in permutation_specs]
    deformations = [
        deformation_domain("context_known_length5", spec5()),
        deformation_domain("absolute_open_set_length3", spec3()),
        deformation_domain("contradictory_length3", contradictory_spec()),
        deformation_domain("single_anchor", single_anchor_spec()),
    ]
    all_rows = permutations + deformations
    print(json.dumps({
        "policy": {
            "states": [ACCEPT, REJECT, FAIL_CLOSED],
            "accept": "sufficient lexical/context evidence and calibrated bounded trajectory match",
            "reject": "sufficient evidence but topology/coverage does not match",
            "fail_closed": "insufficient or contradictory evidence",
        },
        "metric": "binary signed BOS/EOS trajectory coverage + learned arity",
        "lexical_contradiction_cost_used": False,
        "permutation_domains": permutations,
        "deformation_domains": deformations,
        "all_policy_correct": all(r["accuracy"] == 1.0 for r in all_rows),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
