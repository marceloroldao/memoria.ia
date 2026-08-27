from __future__ import annotations

import json

from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate
from role_trajectory_slot_support import slot_support
from role_trajectory_partial_drift import temporal_state


BASE = 8
LEVELS = (4, 8, 16)  # 0.5x, 1x, 2x


def build_gate(payload_n: int, destination_n: int):
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    family_a = ("fonte", "transmite", "sinal", "seguro", "destino")
    family_b = ("origem", "envia", "pacote", "cifrado", "servidor")
    family_c = ("emissor", "remete", "dado", "protegido", "receptor")
    payload_alt = ("fonte", "transmite", "pacote", "seguro", "destino")
    destination_alt = ("fonte", "transmite", "sinal", "seguro", "servidor")

    obs = [" ".join(family_a), " ".join(family_b), " ".join(family_c)] * BASE
    obs += [" ".join(payload_alt)] * payload_n
    obs += [" ".join(destination_alt)] * destination_n
    gate.observe(obs)

    gate.register_role("source", ["fonte", "origem", "emissor"])
    gate.register_role("action", ["transmite", "envia", "remete"])
    gate.register_role("payload", ["sinal", "pacote", "dado"])
    gate.register_role("quality", ["seguro", "cifrado", "protegido"])
    gate.register_role("destination", ["destino", "servidor", "receptor"])
    gate.register_pattern(("source", "action", "payload", "quality", "destination"))
    return gate


def delta(gate, left: str, old: str, new: str) -> float:
    return slot_support(gate, left, 1, old) - slot_support(gate, left, 1, new)


def expected_state(n: int) -> str:
    return "stable" if n < BASE else "uncertain" if n == BASE else "regime_shift"


def main():
    clean = build_gate(0, 0)
    assert clean.calibrate()
    deadband = clean._margin / 2.0
    rows = []
    all_passed = True

    for payload_n in LEVELS:
        for destination_n in LEVELS:
            gate = build_gate(payload_n, destination_n)
            p_delta = delta(gate, "transmite", "sinal", "pacote")
            d_delta = delta(gate, "seguro", "destino", "servidor")
            p_state = temporal_state(p_delta, deadband)
            d_state = temporal_state(d_delta, deadband)
            anchor = slot_support(gate, "fonte", 1, "transmite")

            # Each slot should reflect its own evidence count regardless of the other slot.
            ok = (
                p_state == expected_state(payload_n)
                and d_state == expected_state(destination_n)
                and anchor >= 0.999999
            )
            all_passed = all_passed and ok
            rows.append({
                "payload_n": payload_n,
                "payload_ratio": payload_n / BASE,
                "payload_delta": p_delta,
                "payload_state": p_state,
                "destination_n": destination_n,
                "destination_ratio": destination_n / BASE,
                "destination_delta": d_delta,
                "destination_state": d_state,
                "unchanged_anchor_support": anchor,
                "state_vector": [p_state, d_state],
                "passed": ok,
            })

    result = {
        "experiment": "asynchronous slot drift matrix",
        "principle": "temporal state is local: independently changing slots must preserve their own hysteresis state without cross-contamination",
        "deadband": deadband,
        "rows": rows,
        "summary": {"total": len(rows), "passed": sum(r["passed"] for r in rows), "all_passed": all_passed},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
