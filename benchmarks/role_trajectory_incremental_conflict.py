from __future__ import annotations

import json

from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate


def build_gate(base_repeat: int, conflict_repeat: int):
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    base = [
        "fonte transmite sinal destino",
        "origem envia pacote servidor",
        "emissor remete dado receptor",
    ]
    conflict = [
        "destino transmite sinal fonte",
        "servidor envia pacote origem",
        "receptor remete dado emissor",
    ]
    observations = base * base_repeat + conflict * conflict_repeat
    gate.observe(observations)
    gate.register_role("source", ["fonte", "origem", "emissor"])
    gate.register_role("action", ["transmite", "envia", "remete"])
    gate.register_role("payload", ["sinal", "pacote", "dado"])
    gate.register_role("destination", ["destino", "servidor", "receptor"])
    gate.register_pattern(("source", "action", "payload", "destination"))
    return gate


def snapshot(base_repeat: int, conflict_repeat: int):
    gate = build_gate(base_repeat, conflict_repeat)
    calibrated = gate.calibrate()
    probes = [
        "fonte transmite sinal destino",
        "destino transmite sinal fonte",
        "origem envia pacote servidor",
        "servidor envia pacote origem",
    ]
    results = []
    for text in probes:
        r = gate.resolve(text)
        results.append({
            "text": text,
            "decision": r.decision,
            "coverage": r.coverage,
            "threshold": r.threshold,
            "margin": r.margin,
            "reason": r.reason,
        })
    return {
        "base_repeat": base_repeat,
        "conflict_repeat": conflict_repeat,
        "calibrated": calibrated,
        "threshold": gate.threshold,
        "margin": gate._margin,
        "results": results,
    }


def main():
    rows = [snapshot(8, c) for c in (0, 1, 2, 4, 8, 16, 32)]
    output = {
        "experiment": "incremental temporal conflict",
        "principle": "add reverse-direction evidence gradually while keeping role topology fixed",
        "rows": rows,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
