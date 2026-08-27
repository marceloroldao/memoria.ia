from __future__ import annotations

import json

from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate
from role_trajectory_slot_support import slot_support
from role_trajectory_partial_drift import temporal_state


BASE = 8
ALT = 16
RECOVERY_LEVELS = (0, 4, 8, 16, 32)
EPS = 1e-12


def build_gate(recovery_repeat: int):
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)

    family_a = ("fonte", "transmite", "sinal", "seguro", "destino")
    family_b = ("origem", "envia", "pacote", "cifrado", "servidor")
    family_c = ("emissor", "remete", "dado", "protegido", "receptor")
    payload_alt = ("fonte", "transmite", "pacote", "seguro", "destino")

    observations = [" ".join(family_a), " ".join(family_b), " ".join(family_c)] * BASE
    observations += [" ".join(payload_alt)] * ALT
    observations += [" ".join(family_a)] * recovery_repeat
    gate.observe(observations)

    gate.register_role("source", ["fonte", "origem", "emissor"])
    gate.register_role("action", ["transmite", "envia", "remete"])
    gate.register_role("payload", ["sinal", "pacote", "dado"])
    gate.register_role("quality", ["seguro", "cifrado", "protegido"])
    gate.register_role("destination", ["destino", "servidor", "receptor"])
    gate.register_pattern(("source", "action", "payload", "quality", "destination"))
    return gate


def payload_delta(gate) -> float:
    old_support = slot_support(gate, "transmite", 1, "sinal")
    new_support = slot_support(gate, "transmite", 1, "pacote")
    return old_support - new_support


def main():
    clean = ExperimentalTrajectoryPolicyGate(use_native=False)
    base_obs = [
        "fonte transmite sinal seguro destino",
        "origem envia pacote cifrado servidor",
        "emissor remete dado protegido receptor",
    ] * BASE
    clean.observe(base_obs)
    clean.register_role("source", ["fonte", "origem", "emissor"])
    clean.register_role("action", ["transmite", "envia", "remete"])
    clean.register_role("payload", ["sinal", "pacote", "dado"])
    clean.register_role("quality", ["seguro", "cifrado", "protegido"])
    clean.register_role("destination", ["destino", "servidor", "receptor"])
    clean.register_pattern(("source", "action", "payload", "quality", "destination"))
    assert clean.calibrate()
    deadband = clean._margin / 2.0

    rows = []
    deltas = []
    for recovery in RECOVERY_LEVELS:
        gate = build_gate(recovery)
        delta = payload_delta(gate)
        deltas.append(delta)
        rows.append({
            "recovery_repeat": recovery,
            "recovery_vs_original_base": recovery / BASE,
            "delta": delta,
            "state": temporal_state(delta, deadband),
            "old_support": slot_support(gate, "transmite", 1, "sinal"),
            "new_support": slot_support(gate, "transmite", 1, "pacote"),
            "anchor_support": slot_support(gate, "fonte", 1, "transmite"),
        })

    monotonic_recovery = all(b + EPS >= a for a, b in zip(deltas, deltas[1:]))
    starts_shifted = rows[0]["state"] == "regime_shift"
    ends_stable = rows[-1]["state"] == "stable"
    crosses_uncertainty = any(r["state"] == "uncertain" for r in rows)
    anchors_stable = all(r["anchor_support"] >= 0.999999 for r in rows)

    all_passed = monotonic_recovery and starts_shifted and ends_stable and crosses_uncertainty and anchors_stable
    result = {
        "experiment": "temporal relation recovery",
        "principle": "after a competing relation dominates, renewed evidence for the historical relation must move support monotonically back through the uncertainty region without disturbing an unchanged anchor",
        "base_repeat": BASE,
        "alternative_repeat": ALT,
        "deadband": deadband,
        "rows": rows,
        "summary": {
            "monotonic_recovery": monotonic_recovery,
            "starts_shifted": starts_shifted,
            "crosses_uncertainty": crosses_uncertainty,
            "ends_stable": ends_stable,
            "anchors_stable": anchors_stable,
            "all_passed": all_passed,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
