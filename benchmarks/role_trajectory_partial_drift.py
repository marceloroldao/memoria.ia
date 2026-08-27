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


def trajectory_purity(gate, tokens: tuple[str, ...]) -> float:
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


def build_gate(drift_kind: str, drift_repeat: int, base_repeat: int = 8):
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)

    family_a = ("fonte", "transmite", "sinal", "seguro", "destino")
    family_b = ("origem", "envia", "pacote", "cifrado", "servidor")
    family_c = ("emissor", "remete", "dado", "protegido", "receptor")

    observations = [" ".join(family_a), " ".join(family_b), " ".join(family_c)] * base_repeat

    if drift_kind == "boundary":
        alternative = ("fonte", "transmite", "sinal", "seguro", "servidor")
    elif drift_kind == "internal":
        alternative = ("fonte", "transmite", "pacote", "seguro", "destino")
    else:
        raise ValueError(drift_kind)

    observations += [" ".join(alternative)] * drift_repeat
    gate.observe(observations)

    gate.register_role("source", ["fonte", "origem", "emissor"])
    gate.register_role("action", ["transmite", "envia", "remete"])
    gate.register_role("payload", ["sinal", "pacote", "dado"])
    gate.register_role("quality", ["seguro", "cifrado", "protegido"])
    gate.register_role("destination", ["destino", "servidor", "receptor"])
    gate.register_pattern(("source", "action", "payload", "quality", "destination"))

    return gate, family_a, alternative


def temporal_state(delta: float, deadband: float) -> str:
    if delta > deadband:
        return "stable"
    if delta < -deadband:
        return "regime_shift"
    return "uncertain"


def run_kind(kind: str):
    clean_gate, baseline, alternative = build_gate(kind, 0)
    calibrated = clean_gate.calibrate()
    if not calibrated:
        return {"kind": kind, "calibrated": False}

    gap = clean_gate._margin
    deadband = gap / 2.0
    rows = []
    for drift_repeat in (0, 1, 2, 4, 8, 16, 32):
        gate, baseline, alternative = build_gate(kind, drift_repeat)
        base_score = trajectory_purity(gate, baseline)
        alt_score = trajectory_purity(gate, alternative)
        delta = base_score - alt_score
        rows.append({
            "drift_repeat": drift_repeat,
            "ratio": drift_repeat / 8.0,
            "baseline_score": base_score,
            "alternative_score": alt_score,
            "delta": delta,
            "state": temporal_state(delta, deadband),
        })

    return {
        "kind": kind,
        "calibrated": True,
        "structural_gap": gap,
        "temporal_deadband": deadband,
        "baseline": baseline,
        "alternative": alternative,
        "rows": rows,
    }


def main():
    result = {
        "experiment": "partial trajectory drift",
        "principle": "keep role topology valid while replacing one known relation at a boundary or internal position",
        "cases": [run_kind("boundary"), run_kind("internal")],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
