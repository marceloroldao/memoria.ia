from __future__ import annotations

import json

from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate
from role_trajectory_slot_support import slot_support
from role_trajectory_partial_drift import temporal_state


BASE = 8
CYCLES = 6


def build_gate() -> ExperimentalTrajectoryPolicyGate:
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    family_a = ("fonte", "transmite", "sinal", "seguro", "destino")
    family_b = ("origem", "envia", "pacote", "cifrado", "servidor")
    family_c = ("emissor", "remete", "dado", "protegido", "receptor")
    gate.observe([" ".join(family_a), " ".join(family_b), " ".join(family_c)] * BASE)
    gate.register_role("source", ["fonte", "origem", "emissor"])
    gate.register_role("action", ["transmite", "envia", "remete"])
    gate.register_role("payload", ["sinal", "pacote", "dado"])
    gate.register_role("quality", ["seguro", "cifrado", "protegido"])
    gate.register_role("destination", ["destino", "servidor", "receptor"])
    gate.register_pattern(("source", "action", "payload", "quality", "destination"))
    assert gate.calibrate()
    return gate


def slot_delta(gate: ExperimentalTrajectoryPolicyGate) -> float:
    return slot_support(gate, "transmite", 1, "sinal") - slot_support(gate, "transmite", 1, "pacote")


def snapshot(gate: ExperimentalTrajectoryPolicyGate, label: str) -> dict:
    deadband = gate._margin / 2.0
    delta = slot_delta(gate)
    return {
        "label": label,
        "delta": delta,
        "state": temporal_state(delta, deadband),
        "old_support": slot_support(gate, "transmite", 1, "sinal"),
        "new_support": slot_support(gate, "transmite", 1, "pacote"),
        "unchanged_support": slot_support(gate, "fonte", 1, "transmite"),
    }


def main() -> None:
    gate = build_gate()
    alt = "fonte transmite pacote seguro destino"
    old = "fonte transmite sinal seguro destino"
    rows = [snapshot(gate, "baseline")]

    for cycle in range(1, CYCLES + 1):
        # Drive B strongly enough to dominate, then restore A with the same mass.
        gate.observe([alt] * (2 * BASE))
        rows.append(snapshot(gate, f"cycle_{cycle}_B"))
        gate.observe([old] * (2 * BASE))
        rows.append(snapshot(gate, f"cycle_{cycle}_A"))

    b_states = [r for r in rows if r["label"].endswith("_B")]
    a_states = [r for r in rows if r["label"].endswith("_A")]
    stable_anchor = all(r["unchanged_support"] >= 0.999999 for r in rows)
    # We do not require equal magnitudes cycle to cycle; cumulative history may shrink amplitudes.
    # We require sign/state reversibility and no drift in an unrelated slot.
    alternates = all(r["state"] == "regime_shift" and r["delta"] < 0 for r in b_states)
    restores = all(r["state"] == "stable" and r["delta"] > 0 for r in a_states)
    all_passed = stable_anchor and alternates and restores

    result = {
        "experiment": "recurrent temporal cycles",
        "principle": "repeated A→B→A cycles should remain reversible without corrupting unchanged relations",
        "cycles": CYCLES,
        "deadband": gate._margin / 2.0,
        "rows": rows,
        "summary": {
            "stable_anchor": stable_anchor,
            "b_dominance_each_cycle": alternates,
            "a_recovery_each_cycle": restores,
            "all_passed": all_passed,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
