from __future__ import annotations

import json

from memoria_resolutiva.trajectory_policy_gate_experimental import BOS, EOS, ExperimentalTrajectoryPolicyGate


def relation_purity(gate, left: str, offset: int, right: str) -> float:
    profile = gate.router.roles.memory.associator.profiles.get(left)
    if not profile:
        return 0.0
    wanted = profile.get((offset, right), 0)
    total = sum(count for (other_offset, token), count in profile.items() if token == right and other_offset != 0)
    return wanted / total if total else 0.0


def purity_score(gate, tokens: tuple[str, ...]) -> float:
    seq = (BOS,) + tokens + (EOS,)
    radius = gate.router.roles.memory.associator.radius
    values = []
    for i, token in enumerate(seq):
        lo = max(0, i - radius)
        hi = min(len(seq), i + radius + 1)
        for j in range(lo, hi):
            if i != j:
                values.append(relation_purity(gate, token, j - i, seq[j]))
    return sum(values) / max(1, len(values))


def domain(length: int):
    roles = [f"r{i}" for i in range(length)]
    a = [f"a{i}" for i in range(length)]
    b = [f"b{i}" for i in range(length)]
    c = [f"c{i}" for i in range(length)]
    forward = [" ".join(a), " ".join(b), " ".join(c)]
    reverse = [" ".join(reversed(a)), " ".join(reversed(b)), " ".join(reversed(c))]
    anchors = {role: [a[i], b[i], c[i]] for i, role in enumerate(roles)}
    return roles, a, forward, reverse, anchors


def build(length: int, base_repeat: int, conflict_repeat: int):
    roles, probe, forward, reverse, anchors = domain(length)
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    gate.observe(forward * base_repeat + reverse * conflict_repeat)
    for role in roles:
        gate.register_role(role, anchors[role])
    gate.register_pattern(tuple(roles))
    return gate, tuple(probe), tuple(reversed(probe))


def temporal_state(delta: float, margin: float) -> str:
    if delta > margin:
        return "stable"
    if delta < -margin:
        return "regime_shift"
    return "uncertain"


def run_case(length: int, base_repeat: int):
    baseline, forward_tokens, reverse_tokens = build(length, base_repeat, 0)
    if not baseline.calibrate():
        return {"length": length, "base_repeat": base_repeat, "calibrated": False}
    margin = baseline._margin
    points = []
    for conflict_repeat in (0, max(1, base_repeat // 4), max(1, base_repeat // 2), base_repeat, base_repeat * 2, base_repeat * 4):
        gate, forward_tokens, reverse_tokens = build(length, base_repeat, conflict_repeat)
        f = purity_score(gate, forward_tokens)
        r = purity_score(gate, reverse_tokens)
        delta = f - r
        points.append({
            "conflict_repeat": conflict_repeat,
            "ratio": conflict_repeat / base_repeat,
            "forward": f,
            "reverse": r,
            "delta": delta,
            "state": temporal_state(delta, margin),
        })
    states = [p["state"] for p in points]
    monotonic = all(states.index(s) <= states.index(t) for s, t in zip(states, states[1:])) if False else True
    # Stronger, explicit ordering: stable may be followed by uncertain, then regime_shift, never backwards.
    rank = {"stable": 0, "uncertain": 1, "regime_shift": 2}
    monotonic = all(rank[points[i]["state"]] <= rank[points[i+1]["state"]] for i in range(len(points)-1))
    return {
        "length": length,
        "base_repeat": base_repeat,
        "calibrated": True,
        "margin": margin,
        "points": points,
        "state_progression_monotonic": monotonic,
        "starts_stable": points[0]["state"] == "stable",
        "equal_support_uncertain": next(p for p in points if p["ratio"] == 1.0)["state"] == "uncertain",
        "strong_reverse_regime_shift": points[-1]["state"] == "regime_shift",
    }


def main():
    rows = [run_case(length, base) for length in (4, 5, 6) for base in (2, 4, 8, 16)]
    passed = all(
        row.get("calibrated") and row.get("state_progression_monotonic") and row.get("starts_stable")
        and row.get("equal_support_uncertain") and row.get("strong_reverse_regime_shift")
        for row in rows
    )
    print(json.dumps({
        "experiment": "temporal hysteresis scale matrix",
        "rows": rows,
        "summary": {
            "cases": len(rows),
            "passed": sum(1 for row in rows if row.get("calibrated") and row.get("state_progression_monotonic") and row.get("starts_stable") and row.get("equal_support_uncertain") and row.get("strong_reverse_regime_shift")),
            "all_passed": passed,
        },
    }, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
