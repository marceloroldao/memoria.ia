from __future__ import annotations

import json

from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate
from role_trajectory_slot_support import slot_support
from role_trajectory_partial_drift import temporal_state


BASE_REPEAT = 8


def build_gate(drift_repeat: int):
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)

    family_a = ("fonte", "transmite", "sinal", "seguro", "destino")
    family_b = ("origem", "envia", "pacote", "cifrado", "servidor")
    family_c = ("emissor", "remete", "dado", "protegido", "receptor")
    alternative = ("fonte", "transmite", "pacote", "seguro", "servidor")

    observations = [" ".join(family_a), " ".join(family_b), " ".join(family_c)] * BASE_REPEAT
    observations += [" ".join(alternative)] * drift_repeat
    gate.observe(observations)

    gate.register_role("source", ["fonte", "origem", "emissor"])
    gate.register_role("action", ["transmite", "envia", "remete"])
    gate.register_role("payload", ["sinal", "pacote", "dado"])
    gate.register_role("quality", ["seguro", "cifrado", "protegido"])
    gate.register_role("destination", ["destino", "servidor", "receptor"])
    gate.register_pattern(("source", "action", "payload", "quality", "destination"))
    return gate


def slot_delta(gate, left: str, old: str, new: str) -> float:
    return slot_support(gate, left, 1, old) - slot_support(gate, left, 1, new)


def main():
    clean = build_gate(0)
    assert clean.calibrate()
    deadband = clean._margin / 2.0

    rows = []
    all_ok = True
    previous_payload = float("inf")
    previous_destination = float("inf")

    for drift in (0, 1, 2, 4, 8, 16, 32):
        gate = build_gate(drift)
        payload_delta = slot_delta(gate, "transmite", "sinal", "pacote")
        destination_delta = slot_delta(gate, "seguro", "destino", "servidor")
        payload_state = temporal_state(payload_delta, deadband)
        destination_state = temporal_state(destination_delta, deadband)

        unchanged_support = slot_support(gate, "fonte", 1, "transmite")

        if payload_delta > previous_payload + 1e-12 or destination_delta > previous_destination + 1e-12:
            all_ok = False
        previous_payload = payload_delta
        previous_destination = destination_delta

        expected = "stable" if drift < BASE_REPEAT else "uncertain" if drift == BASE_REPEAT else "regime_shift"
        if drift in (0, 1, 2, 4, 8, 16, 32):
            if payload_state != expected or destination_state != expected:
                all_ok = False
        if unchanged_support < 0.999999:
            all_ok = False

        aggregate = (
            "global_regime_shift" if payload_state == destination_state == "regime_shift"
            else "global_uncertain" if "uncertain" in (payload_state, destination_state)
            else "local_stable"
        )

        rows.append({
            "drift": drift,
            "ratio": drift / BASE_REPEAT,
            "payload_delta": payload_delta,
            "payload_state": payload_state,
            "destination_delta": destination_delta,
            "destination_state": destination_state,
            "unchanged_anchor_support": unchanged_support,
            "aggregate": aggregate,
        })

    result = {
        "experiment": "multi-slot temporal drift",
        "principle": "independent slot competition should preserve unchanged relations while multiple changed relations cross temporal hysteresis together",
        "deadband": deadband,
        "rows": rows,
        "all_passed": all_ok,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
